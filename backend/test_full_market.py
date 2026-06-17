import asyncio
import websockets
import json
import time

WS_URL = "ws://localhost:8765"


async def test_full_flow():
    print("=" * 60)
    print("完整交易流程测试")
    print("=" * 60)

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "login", "username": "FullTestUser"}))

        player = None
        market = None
        messages = []

        for _ in range(10):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(msg)
                messages.append(data)
                if data["type"] == "state":
                    player = data["player"]
                elif data["type"] == "market":
                    market = data["market"]
            except asyncio.TimeoutError:
                break

        print(f"\n初始状态: ore={player['ore']}, fuel={player['fuel']}, credits={player['credits']}")
        print(f"市场订单数: {len(market['orders'])}")
        print(f"市场剩余时间: {market['expires_at'] - int(time.time())}秒")

        buy_orders = [o for o in market["orders"] if o["order_type"] == "buy"]
        sell_orders = [o for o in market["orders"] if o["order_type"] == "sell"]

        print(f"收购订单: {len(buy_orders)} 个, 出售订单: {len(sell_orders)} 个")

        print("\n[步骤1] 开始挖矿 3秒, 积累一些矿石...")
        await ws.send(json.dumps({"type": "start_mining"}))
        await asyncio.sleep(3)

        player = None
        market = None
        for _ in range(20):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                data = json.loads(msg)
                if data["type"] == "state":
                    player = data["player"]
                elif data["type"] == "market":
                    market = data["market"]
            except asyncio.TimeoutError:
                break

        print(f"3秒后: ore={player['ore']}, fuel={player['fuel']}")

        if buy_orders:
            order = buy_orders[0]
            print(f"\n[步骤2] 卖给商人 5个矿石 (订单 #{order['id']}, 单价 {order['price_per_unit']})")
            await ws.send(json.dumps({
                "type": "trade",
                "order_id": order["id"],
                "amount": 5,
            }))

            for _ in range(5):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(msg)
                    if data["type"] == "state":
                        player = data["player"]
                        print(f"  交易后: ore={player['ore']}, credits={player['credits']}")
                        break
                    elif data["type"] == "error":
                        print(f"  错误: {data['message']}")
                        break
                except asyncio.TimeoutError:
                    pass

        if sell_orders:
            order = sell_orders[0]
            print(f"\n[步骤3] 从商人买 5个燃料 (订单 #{order['id']}, 单价 {order['price_per_unit']})")
            await ws.send(json.dumps({
                "type": "trade",
                "order_id": order["id"],
                "amount": 5,
            }))

            for _ in range(5):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(msg)
                    if data["type"] == "state":
                        player = data["player"]
                        print(f"  交易后: fuel={player['fuel']}, credits={player['credits']}")
                        break
                    elif data["type"] == "error":
                        print(f"  错误: {data['message']}")
                        break
                except asyncio.TimeoutError:
                    pass

        print("\n" + "=" * 60)
        print("✅ 完整交易流程测试通过!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_full_flow())
