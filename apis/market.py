from .base import BaseFunc


class Market(BaseFunc):
    def __init__(self, symbol, exchange, *args, **kwargs):
        super(Market, self).__init__(symbol, exchange, *args, **kwargs)
        # 初始化一些交易参数
        self.market = self.exchange.markets[self.symbol]
        self.precision = self.market.get("precision")
        self.limits = self.market.get("limits")
        self.info = self.market.get('info')
        # 单位精度，比如Btc在gate中是0.0001
        self.amount_size = self.market.get('contractSize') if self.market.get('contractSize') else 1

        # 初始化精度
        self.price_precision = self.precision.get('price')  # 价格精度
        self.amount_precision = self.precision.get('amount')  # 交易金额精度
        self.order_price_deviate = self.info.get('order_price_deviate')  # gate目前使用，最大交易偏差

        # 交易信息
        self.max_level = min(self.limits.get('leverage').get('max'), 100)

    @BaseFunc.while_loop
    def get_now_price(self):
        """
        获取当前价格
        :return:
        """
        ticker = self.handle('fetch_ticker', self.symbol)
        if ticker:
            return ticker['last']

    @BaseFunc.while_loop
    def get_order_books(self, side=None, num=None):
        """
        获取挂单列表
        :param side: buy-返回买单列表，sell-返回卖单列表
        :param num: 返回具体几号买卖单，1-10分别对应的买卖1-10
        :return:
        """
        orders = self.handle('fetch_order_book', self.symbol)
        if not orders:
            return False

        if side == 'buy':
            order_list = orders.get('bids')
        elif side == 'sell':
            order_list = orders.get('asks')
        else:
            return orders
        if num:
            return order_list[num - 1]
        return order_list

    def get_can_order_price(self, price):
        """
        根据精度计算出可以交易的价格
        :param price:
        :return:
        """
        new_price = self.handle('price_to_precision', self.symbol, price)
        if new_price:
            return float(new_price)
        return False

    def get_can_order_amount(self, amount, order_price=None):
        """
        根据精度计算出可以购买的amount的最小单位
        1. 先计算出实际的交易所amount=amount * self.amount_size
        :param order_price:
        :param amount:
        :return:
        """
        if amount < self.get_min_amount(order_price):
            return 0

        # if self.exchange.name == 'Gate.io':
        #     return self.handle('amount_to_precision', self.symbol, amount)

        # 先计算出交易所的amount
        amount = round(amount / self.amount_size, 15)
        amount = self.handle('amount_to_precision', self.symbol, amount)
        if not amount:
            return False

        return float(amount) * self.amount_size

    def get_min_amount(self, order_price=None):
        """
        获取最小amount, 这里单位需要统一，比如50000元的BTC，0.1amount就是5000元
        :return:
        """

        min_cost = self.limits.get('cost').get('min')
        min_amount = self.limits.get('amount').get('min')
        if self.exchange.name == 'Gate.io':
            # 如果是Gate.io, 最小单位就是min_amount
            return min_amount * self.amount_size

        if not order_price:
            order_price = self.get_now_price()

        # 最小成本/指定的价格=最小购买的amount, 最小amount/最小单位amount=amount的倍数，在让倍数+1.即可获取最小的购买金额
        min_cost_amount = min_cost / order_price
        min_buy_ratio = int(min_cost_amount / min_amount)
        if min_cost_amount % min_amount != 0:
            min_buy_ratio += 1

        return min_buy_ratio * min_amount * self.amount_size

    def set_level(self, level):
        """
        设置杠杆
        :param level:
        :return:
        """
        params = {}
        if self.exchange.id == 'gate':
            params['cross_leverage_limit'] = level
        res = self.handle('set_leverage', level, self.symbol, params=params)
        return res

    def set_max_level(self):
        """
        设置最大杠杆倍数
        """
        self.set_level(self.max_level)
