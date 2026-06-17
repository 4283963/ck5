import asyncio
import websockets
import json
import time

WS_URL = "ws://localhost:8765"


async def test_market():
    print("=" * 60)
    print("TEST: 黑市商人功能")
    print("=" * 60)

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "login", "username": "MarketTest"}))

        player = None
        market = None

        for _ in range(5):
            resp = json.loads(await ws.recv())
            if resp["type"] == "state":
                player = resp["player"]
            elif resp["type"] == "market":
                market = resp["market"]
            if player and market:
                break

        print(f"\n[玩家状态]")
        print(f"  矿石: {player['ore']}")
        print(f"  燃料: {player['fuel']}")
        print(f"  星币: {player['credits']}")

        print(f"\n[市场订单] (有效期 {market['expires_at'] - int(time.time())}秒)")
        for order in market["orders"]:
            direction = "收购" if order["order_type"] == "buy" else "出售"
            print(f"  - {direction} {order['item']}: {order['quantity']}个 @ {order['price_per_unit']}星币/个")

        buy_orders = [o for o in market["orders"] if o["order_type"] == "buy"]
        sell_orders = [o for o in market["orders"] if o["order_type"] == "sell"]

        if buy_orders:
            order = buy_orders[0]
            print(f"\n[测试] 卖给商人 5 个矿石 (订单 #{order['id']})")
            await ws.send(json.dumps({
                "type": "trade",
                "order_id": order["id"],
                "amount": 5,
            }))
            for _ in range(3):
                resp = json.loads(await ws.recv())
                if resp["type"] == "state":
                    p = resp["player"]
                    print(f"  交易后 - 矿石: {p['ore']}, 星币: {p['credits']}")
                elif resp["type"] == "error":
                    print(f"  错误: {resp['message']}")

        if sell_orders:
            order = sell_orders[0]
            print(f"\n[测试] 从商人购买 5 个燃料 (订单 #{order['id']})")
            await ws.send(json.dumps({
                "type": "trade",
                "order_id": order["id"],
                "amount": 5,
            }))
            for _ in range(3):
                resp = json.loads(await ws.recv())
                if resp["type"] == "state":
                    p = resp["player"]
                    print(f"  交易后 - 燃料: {p['fuel']}, 星币: {p['credits']}")
                elif resp["type"] == "error":
                    print(f"  错误: {resp['message']}")

        print("\n✅ 黑市商人功能测试完成")


if __name__ == "__main__":
    asyncio.run(test_market())
