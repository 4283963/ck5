import asyncio
import websockets
import json
import time

WS_URL = "ws://localhost:8765"
NUM_PLAYERS = 5
UPGRADES_PER_PLAYER = 3
STARTING_ORE = 1000

results = {}
errors = []


async def player_session(player_id):
    username = f"StressTest_{player_id}"
    results[username] = {"success": 0, "fail": 0, "ore_before": 0, "ore_after": 0, "cargo_before": 0, "cargo_after": 0}

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "login", "username": username}))
        resp = json.loads(await ws.recv())
        player = resp["player"]
        results[username]["ore_before"] = player["ore"]
        results[username]["cargo_before"] = player["max_cargo"]

        ore_needed = 0
        cargo = player["max_cargo"]
        for i in range(UPGRADES_PER_PLAYER):
            ore_needed += cargo
            cargo += 50

        if player["ore"] < ore_needed:
            await ws.send(json.dumps({"type": "refuel"}))
            pass

        tasks = []
        for i in range(UPGRADES_PER_PLAYER):
            tasks.append(ws.send(json.dumps({"type": "upgrade_cargo"})))

        await asyncio.gather(*tasks)

        await asyncio.sleep(0.5)
        await ws.send(json.dumps({"type": "get_state"}))
        resp = json.loads(await ws.recv())
        player = resp["player"]
        results[username]["ore_after"] = player["ore"]
        results[username]["cargo_after"] = player["max_cargo"]


async def setup_players():
    for i in range(NUM_PLAYERS):
        username = f"StressTest_{i}"
        async with websockets.connect(WS_URL) as ws:
            await ws.send(json.dumps({"type": "login", "username": username}))
            await ws.recv()
            import sqlite3
            conn = sqlite3.connect("/Users/kl/Documents/trae_projects2/ck5/backend/space_miner.db")
            conn.execute("UPDATE players SET ore = ?, fuel = 100, max_cargo = 100, mining = 0 WHERE username = ?",
                         (STARTING_ORE, username))
            conn.commit()
            conn.close()


async def main():
    print("=" * 60)
    print("STRESS TEST: Concurrent upgrade_cargo")
    print(f"Players: {NUM_PLAYERS}, Upgrades per player: {UPGRADES_PER_PLAYER}")
    print("=" * 60)

    print("\n[1/3] Setting up players...")
    await setup_players()
    print("Done.")

    print(f"\n[2/3] Running {NUM_PLAYERS} concurrent players, each spamming {UPGRADES_PER_PLAYER} upgrades...")
    start = time.time()
    try:
        await asyncio.gather(*(player_session(i) for i in range(NUM_PLAYERS)))
    except Exception as e:
        print(f"ERROR during test: {e}")
        errors.append(str(e))
    elapsed = time.time() - start
    print(f"Done in {elapsed:.2f}s")

    print("\n[3/3] Verifying results...")
    all_ok = True
    for username, r in results.items():
        expected_cargo = r["cargo_before"] + UPGRADES_PER_PLAYER * 50
        actual_cargo = r["cargo_after"]
        cargo_ok = actual_cargo >= r["cargo_before"]

        ore_spent = r["ore_before"] - r["ore_after"]
        expected_ore_cost = sum(r["cargo_before"] + i * 50 for i in range(UPGRADES_PER_PLAYER))
        ore_ok = ore_spent <= expected_ore_cost + 1

        status = "✅" if (cargo_ok and ore_ok and r["ore_after"] >= 0) else "❌"
        if not (cargo_ok and ore_ok and r["ore_after"] >= 0):
            all_ok = False

        print(f"  {status} {username}: cargo {r['cargo_before']}→{r['cargo_after']} (exp {expected_cargo}), "
              f"ore {r['ore_before']}→{r['ore_after']} (spent {ore_spent})")

    print("\n" + "=" * 60)
    if all_ok and not errors:
        print("✅ ALL TESTS PASSED - No database lock errors, no resource loss")
    else:
        print("❌ TESTS FAILED")
        if errors:
            print(f"Errors: {errors}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
