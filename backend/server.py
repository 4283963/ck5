import asyncio
import json
import logging
import websockets
from websockets.server import WebSocketServerProtocol

from database import init_db, get_player, create_player, update_player

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("space_miner")

MINING_ORE_PER_SECOND = 2
FUEL_PER_SECOND = 1
OXYGEN_PER_SECOND = 0

connected_clients = {}
mining_players = set()


def sanitize_player(player):
    return {
        "username": player["username"],
        "ore": player["ore"],
        "fuel": player["fuel"],
        "max_cargo": player["max_cargo"],
        "oxygen": player["oxygen"],
        "max_oxygen": player["max_oxygen"],
        "mining": bool(player["mining"]),
    }


async def send_state(websocket, player):
    state = {
        "type": "state",
        "player": sanitize_player(player),
    }
    await websocket.send(json.dumps(state))


async def broadcast_mining_update(username):
    player = get_player(username)
    if not player:
        return
    state = sanitize_player(player)
    for ws, name in list(connected_clients.items()):
        if name == username:
            try:
                await ws.send(json.dumps({"type": "state", "player": state}))
            except Exception:
                pass


def tick_mining():
    to_remove = []
    for username in list(mining_players):
        player = get_player(username)
        if not player:
            to_remove.append(username)
            continue

        if player["fuel"] <= 0:
            player["mining"] = 0
            mining_players.discard(username)
            update_player(username, mining=0)
            continue

        new_ore = min(player["ore"] + MINING_ORE_PER_SECOND, player["max_cargo"])
        new_fuel = max(player["fuel"] - FUEL_PER_SECOND, 0)

        ore_added = new_ore - player["ore"]
        if ore_added < MINING_ORE_PER_SECOND and player["ore"] < player["max_cargo"]:
            pass

        update_player(
            username,
            ore=new_ore,
            fuel=new_fuel,
            mining=1 if new_fuel > 0 else 0,
        )

        if new_fuel <= 0:
            mining_players.discard(username)

    for username in to_remove:
        mining_players.discard(username)


async def game_loop():
    while True:
        await asyncio.sleep(1)
        tick_mining()
        for username in list(mining_players):
            asyncio.create_task(broadcast_mining_update(username))


async def handle_message(websocket, message):
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        return

    msg_type = data.get("type")
    username = connected_clients.get(websocket)

    if msg_type == "login":
        name = data.get("username", "").strip()
        if not name or len(name) > 20:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid username",
            }))
            return

        player = create_player(name)
        connected_clients[websocket] = name
        logger.info(f"Player logged in: {name}")
        await send_state(websocket, player)

        if player["mining"]:
            mining_players.add(name)
        return

    if not username:
        await websocket.send(json.dumps({
            "type": "error",
            "message": "Not logged in",
        }))
        return

    if msg_type == "start_mining":
        player = get_player(username)
        if not player:
            return
        if player["fuel"] <= 0:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Out of fuel!",
            }))
            return
        update_player(username, mining=1)
        mining_players.add(username)
        await send_state(websocket, get_player(username))

    elif msg_type == "stop_mining":
        update_player(username, mining=0)
        mining_players.discard(username)
        await send_state(websocket, get_player(username))

    elif msg_type == "refuel":
        player = get_player(username)
        if not player:
            return
        cost = 10
        fuel_add = 20
        if player["ore"] < cost:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Not enough ore to refuel!",
            }))
            return
        new_fuel = min(player["fuel"] + fuel_add, 100)
        actual_add = new_fuel - player["fuel"]
        actual_cost = int(actual_add * (cost / fuel_add))
        update_player(
            username,
            ore=player["ore"] - actual_cost,
            fuel=new_fuel,
        )
        await send_state(websocket, get_player(username))

    elif msg_type == "upgrade_cargo":
        player = get_player(username)
        if not player:
            return
        cost = player["max_cargo"]
        if player["ore"] < cost:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Need {cost} ore to upgrade cargo!",
            }))
            return
        update_player(
            username,
            ore=player["ore"] - cost,
            max_cargo=player["max_cargo"] + 50,
        )
        await send_state(websocket, get_player(username))

    elif msg_type == "get_state":
        player = get_player(username)
        if player:
            await send_state(websocket, player)


async def handler(websocket: WebSocketServerProtocol):
    logger.info("New connection")
    try:
        async for message in websocket:
            await handle_message(websocket, message)
    except websockets.exceptions.ConnectionClosed:
        logger.info("Connection closed")
    finally:
        username = connected_clients.pop(websocket, None)
        if username:
            logger.info(f"Player disconnected: {username}")
            mining_players.discard(username)


async def main():
    init_db()
    logger.info("Database initialized")

    asyncio.create_task(game_loop())
    logger.info("Game loop started")

    async with websockets.serve(handler, "0.0.0.0", 8765):
        logger.info("Server started on ws://0.0.0.0:8765")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
