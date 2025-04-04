import time
import unittest

import ccxt

from apis import CcxtApis
from datetime import datetime

exchange = CcxtApis(exchange_name="gate",
                    api_key="5a6681b2d085c074c56d41b3e6dfc1d7",
                    api_secret="7cf1d964c609a5740276bec08e7303c20dad44e63e09efcf1613086ec331d1d9")
# exchange = ccxt.binance()
symbol = 'BTC/USDT:USDT'
# symbol = "SOL/USDT:USDT"
if __name__ == '__main__':
    exchange.exchange.load_markets()
    order_id = '1908159063661740032'
    open_time = '1743730086'

    kd = exchange.kdata(symbol)
    o = exchange.order(symbol)
    u = exchange.user(symbol)
    e = exchange.exchange
    b = e.fetch_closed_orders(symbol, params={'status': "open"})
    a = e.fetchPositionsHistory([symbol])
    print(a)
    # '1908084846081605632'
    print(123)
    # while True:
    #     t1 = time.time()
    #     now_price = m.get_now_price()
    #     print(now_price)
    #     t2 = time.time()
    #     print(t2-t1)
