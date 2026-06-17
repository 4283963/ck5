import asyncio
import websockets
import json

WS_URL = "ws://localhost:8765"


async def test_trade():
    print("=" * 60)
    print("精确交易测试 (停止挖矿后交易)")
    print("=" * 60)

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "login", "username": "PreciseTest"}))

        player = None
        market = None
        all_msgs = []

        for _ in range(10):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(msg)
                all_msgs.append(data)
                if data["type"] == "state":
                    player = data["player"]
                elif data["type"] == "market":
                    market = data["market"]
            except asyncio.TimeoutError:
                break

        print(f"\n初始: ore={player['ore']}, fuel={player['fuel']}, credits={player['credits']}")

        await ws.send(json.dumps({"type": "stop_mining"}))
        await asyncio.sleep(0.5)
        for _ in range(5):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                data = json.loads(msg)
                if data["type"] == "state":
                    player = data["player"]
            except asyncio.TimeoutError:
                pass

        print(f"停止挖矿后: ore={player['ore']}, fuel={player['fuel']}, credits={player['credits']}")

        buy_orders = [o for o in market["orders"] if o["order_type"] == "buy"]
        sell_orders = [o for o in market["orders"] if o["order_type"] == "sell"]

        if buy_orders:
            order = buy_orders[0]
            print(f"\n[测试1] 卖矿石 (订单 #{order['id']}, {order['order_type']}, 单价 {order['price_per_unit']})")
            print(f"  交易前: ore={player['ore']}, credits={player['credits']}")

            await ws.send(json.dumps({"type": "trade", "order_id": order["id"], "amount": 1}))

            for _ in range(5):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(msg)
                    if data["type"] == "state":
                        player = data["player"]
                        break
                    elif data["type"] == "error":
                        print(f"  错误: {data['message']}")
                        break
                except asyncio.TimeoutError:
                    pass

            print(f"  交易后: ore={player['ore']}, credits={player['credits']}")
            ore_diff = player["ore"] - (player["ore"] - 0)
            print(f"  验证: 矿石应该减少1, 星币应该增加{order['price_per_unit']}")

        if sell_orders:
            order = sell_orders[0]
            print(f"\n[测试2] 买燃料 (订单 #{order['id']}, {order['order_type']}, 单价 {order['price_per_unit']})")
            fuel_before = player["fuel"]
            credits_before = player["credits"]
            print(f"  交易前: fuel={fuel_before}, credits={credits_before}")

            await ws.send(json.dumps({"type": "trade", "order_id": order["id"], "amount": 5}))

            for _ in range(5):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(msg)
                    if data["type"] == "state":
                        player = data["player"]
                        break
                    elif data["type"] == "error":
                        print(f"  错误: {data['message']}")
                        break
                except asyncio.TimeoutError:
                    pass

            fuel_after = player["fuel"]
            credits_after = player["credits"]
            print(f"  交易后: fuel={fuel_after}, credits={credits_after}")
            print(f"  变化: fuel+{fuel_after-fuel_before}, credits{credits_after-credits_before}")

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_trade())
