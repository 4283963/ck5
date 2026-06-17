import sys
sys.path.insert(0, '.')

from database import init_db, get_conn, get_market_orders, execute_market_trade, get_player, create_player, close_conn

init_db()

create_player('DBTestUser')
conn = get_conn()
conn.execute('UPDATE players SET ore = 100, credits = 100, fuel = 50 WHERE username = "DBTestUser"')
conn.commit()

p = get_player('DBTestUser')
print(f'玩家初始: ore={p["ore"]}, fuel={p["fuel"]}, credits={p["credits"]}')

orders = get_market_orders()
print(f'\n市场订单 ({len(orders)} 个):')
for o in orders:
    print(f'  #{o["id"]} {o["order_type"]} {o["item"]}: {o["remaining"]}/{o["quantity"]} @ {o["price_per_unit"]}')

buy_orders = [o for o in orders if o['order_type'] == 'buy']
sell_orders = [o for o in orders if o['order_type'] == 'sell']

if buy_orders:
    o = buy_orders[0]
    print(f'\n[测试] 卖矿石 10个 (订单 #{o["id"]})')
    result, err = execute_market_trade('DBTestUser', o['id'], 10)
    if err:
        print(f'  错误: {err}')
    else:
        print(f'  成功: 数量={result["amount"]}, 收入={result["total_price"]}')
        p = result['player']
        print(f'  玩家: ore={p["ore"]}, credits={p["credits"]}')

if sell_orders:
    o = sell_orders[0]
    print(f'\n[测试] 买燃料 10个 (订单 #{o["id"]})')
    result, err = execute_market_trade('DBTestUser', o['id'], 10)
    if err:
        print(f'  错误: {err}')
    else:
        print(f'  成功: 数量={result["amount"]}, 花费={result["total_price"]}')
        p = result['player']
        print(f'  玩家: fuel={p["fuel"]}, credits={p["credits"]}')

print('\n✅ 数据库层测试完成')
close_conn()
