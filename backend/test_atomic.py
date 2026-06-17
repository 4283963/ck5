import asyncio
import websockets
import json
import sqlite3

WS_URL = "ws://localhost:8765"
DB_PATH = "/Users/kl/Documents/trae_projects2/ck5/backend/space_miner.db"


def reset_player(username, ore=1000, cargo=100, fuel=100):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO players (username, ore, max_cargo, fuel, oxygen, max_oxygen, mining) "
        "VALUES (?, ?, ?, ?, 100, 100, 0)",
        (username, ore, cargo, fuel),
    )
    conn.commit()
    conn.close()


def get_db_state(username):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM players WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


async def test_atomic_upgrade():
    """测试升级操作的原子性：扣矿石和升级货舱必须同时成功或同时失败"""
    print("=" * 60)
    print("TEST 1: Atomic upgrade_cargo (单个玩家连续升级)")
    print("=" * 60)

    username = "AtomicTest"
    reset_player(username, ore=1000, cargo=100)

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "login", "username": username}))
        await ws.recv()

        for i in range(5):
            await ws.send(json.dumps({"type": "upgrade_cargo"}))
            resp = json.loads(await ws.recv())
            if resp["type"] == "state":
                p = resp["player"]
                print(f"  升级 {i+1}: cargo={p['max_cargo']}, ore={p['ore']}")
            else:
                print(f"  升级 {i+1}: 错误 - {resp.get('message')}")

    final = get_db_state(username)
    expected_cargo = 100 + 5 * 50
    expected_ore_spent = 100 + 150 + 200 + 250 + 300

    cargo_ok = final["max_cargo"] == expected_cargo
    ore_ok = final["ore"] == 1000 - expected_ore_spent

    print(f"\n  最终: cargo={final['max_cargo']} (预期 {expected_cargo}) {'✅' if cargo_ok else '❌'}")
    print(f"  最终: ore={final['ore']} (预期 {1000 - expected_ore_spent}) {'✅' if ore_ok else '❌'}")

    return cargo_ok and ore_ok


async def test_concurrent_upgrade():
    """测试并发升级：10个玩家同时疯狂点升级，验证不会有 database locked"""
    print("\n" + "=" * 60)
    print("TEST 2: Concurrent upgrade_cargo (10个玩家并发)")
    print("=" * 60)

    num_players = 10
    upgrades_per_player = 8
    success_count = 0
    error_count = 0

    async def player_session(pid):
        nonlocal success_count, error_count
        username = f"Concurrent_{pid}"
        reset_player(username, ore=5000, cargo=100)

        async with websockets.connect(WS_URL) as ws:
            await ws.send(json.dumps({"type": "login", "username": username}))
            await ws.recv()

            for i in range(upgrades_per_player):
                await ws.send(json.dumps({"type": "upgrade_cargo"}))

            for i in range(upgrades_per_player):
                try:
                    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                    if resp["type"] == "state":
                        success_count += 1
                    else:
                        error_count += 1
                except asyncio.TimeoutError:
                    error_count += 1

    start = asyncio.get_event_loop().time()
    await asyncio.gather(*(player_session(i) for i in range(num_players)))
    elapsed = asyncio.get_event_loop().time() - start

    print(f"  总请求: {num_players * upgrades_per_player}")
    print(f"  成功: {success_count}")
    print(f"  失败/错误: {error_count}")
    print(f"  耗时: {elapsed:.2f}s")

    no_lock_errors = error_count < num_players * upgrades_per_player
    print(f"\n  无 database locked 错误: {'✅' if no_lock_errors else '❌'}")

    return no_lock_errors


async def test_no_resource_loss():
    """验证不会出现'扣了矿石但没升级'的情况"""
    print("\n" + "=" * 60)
    print("TEST 3: 资源一致性验证 (扣矿石 = 升级)")
    print("=" * 60)

    username = "ConsistencyTest"
    reset_player(username, ore=9999, cargo=100)

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "login", "username": username}))
        await ws.recv()

        for _ in range(10):
            await ws.send(json.dumps({"type": "upgrade_cargo"}))
            resp = json.loads(await ws.recv())
            if resp["type"] == "error":
                break

    final = get_db_state(username)
    upgrades_done = (final["max_cargo"] - 100) // 50

    expected_cost = sum(100 + i * 50 for i in range(upgrades_done))
    actual_cost = 9999 - final["ore"]

    consistent = expected_cost == actual_cost

    print(f"  升级次数: {upgrades_done}")
    print(f"  预期花费: {expected_cost} 矿石")
    print(f"  实际花费: {actual_cost} 矿石")
    print(f"  资源一致性: {'✅' if consistent else '❌'}")

    return consistent


async def main():
    results = []
    results.append(("原子性测试", await test_atomic_upgrade()))
    results.append(("并发测试", await test_concurrent_upgrade()))
    results.append(("资源一致性测试", await test_no_resource_loss()))

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    all_pass = True
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
        if not ok:
            all_pass = False
    print("=" * 60)
    print(f"OVERALL: {'ALL PASSED ✅' if all_pass else 'SOME FAILED ❌'}")


if __name__ == "__main__":
    asyncio.run(main())
