import asyncio
import json
import logging
import websockets
from websockets.server import WebSocketServerProtocol

from database import (
    init_db,
    get_player,
    create_player,
    update_player,
    upgrade_cargo,
    refuel,
    mining_tick,
    close_conn,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("space_miner")

MINING_ORE_PER_SECOND = 2
FUEL_PER_SECOND = 1

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
        player = mining_tick(username, MINING_ORE_PER_SECOND, FUEL_PER_SECOND)
        if not player:
            to_remove.append(username)
            continue

        if not player["mining"]:
            to_remove.append(username)

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
        player = update_player(username, mining=1)
        mining_players.add(username)
        await send_state(websocket, player)

    elif msg_type == "stop_mining":
        player = update_player(username, mining=0)
        mining_players.discard(username)
        await send_state(websocket, player)

    elif msg_type == "refuel":
        player, err = refuel(username)
        if err:
            await websocket.send(json.dumps({
                "type": "error",
                "message": err,
            }))
            return
        await send_state(websocket, player)

    elif msg_type == "upgrade_cargo":
        player, err = upgrade_cargo(username)
        if err:
            await websocket.send(json.dumps({
                "type": "error",
                "message": err,
            }))
            return
        await send_state(websocket, player)

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
    try:
        asyncio.run(main())
    finally:
        close_conn()
