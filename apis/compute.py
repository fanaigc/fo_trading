from .base import BaseFunc
from .market import Market
from .user import User


class Compute(BaseFunc):
    def __init__(self, symbol, exchange, *args, **kwargs):
        super(Compute, self).__init__(symbol, exchange, *args, **kwargs)
        # 初始化一些交易参数
        self.m = Market(symbol=symbol, exchange=self.exchange, *args, **kwargs)
        self.u = User(symbol=symbol, exchange=self.exchange, *args, **kwargs)

    def get_buy_amount_for_stop_price(self, side, stop_loss_price, max_loss_money, now_price=0):
        """
        根据止损几个和最大亏损价格计算投资的amount
        这个amount应该忽略所有的交易所特性，只获得对应价格的amount，比如比特币50000元，amount-0.1就是购买5000元
        :param side:
        :param now_price: 购买价格
        :param stop_loss_price:
        :param max_loss_money:
        :return:
        """
        commission = 0.05 / 100  # 手续费 0.05%
        slip_point = 0.01 / 100  # 滑点 0.01%
        if not now_price:
            now_price = self.m.get_now_price()

        if side == 'long' and now_price > stop_loss_price:
            # 多头止损
            now_price = now_price * (1 + slip_point)
            stop_loss_price = stop_loss_price * (1 - slip_point)
            amount = max_loss_money / (now_price - stop_loss_price +
                                       now_price * commission + stop_loss_price * commission)
        elif side == 'short' and now_price < stop_loss_price:
            # 空头止损
            now_price = now_price * (1 - slip_point)
            stop_loss_price = stop_loss_price * (1 + slip_point)
            amount = max_loss_money / (stop_loss_price - now_price +
                                       now_price * commission + stop_loss_price * commission)
        else:
            return 0

        # amount = amount / self.m.amount_size
        # amount = self.exchange.amount_to_precision(self.symbol, amount)
        min_amount = self.m.get_min_amount()

        if float(amount) >= min_amount:
            # return amount
            # if self.exchange.name == 'Gate.io':
            #     return self.m.get_can_order_amount(amount)
            return self.m.get_can_order_amount(amount)
        return 0

    def get_max_loss(self, side, stop_loss_price):
        """
        获取最大亏损金额
        正数是亏损，负数是赚取
        :param side:
        :param stop_loss_price:
        :return:
        """
        buy_price = self.u.get_position_avg_buy_price(side)
        now_amount = self.u.get_position_amount(side)

        commission = 0.05 / 100  # 手续费 0.05%
        buy_commission = buy_price * commission * now_amount
        stop_loss_commission = stop_loss_price * commission * now_amount
        all_commission = buy_commission + stop_loss_commission
        max_loss = 0
        if side == 'long':
            max_loss = (buy_price - stop_loss_price) * now_amount
        elif side == 'short':
            max_loss = (stop_loss_price - buy_price) * now_amount
        return max_loss + all_commission

    @staticmethod
    def get_max_lever(entry_price, exit_price):
        """
        获取最大杠杆等级
        # 1. 计算入场和退出亏损的百分比
        # 2. 计算杠杆 100 / 最大亏损百分比
        # 3. 优化杠杆 int后 - 1 最小是1
        :param entry_price: 入场价格
        :param exit_price:  退出价格
        :return:
        """
        loss_rate = abs(entry_price - exit_price) / entry_price * 100
        max_lever = 100 / loss_rate
        if max_lever < 1:
            raise ValueError("最大杠杆小于1，不可以进行交易！！")

        return max(int(max_lever) - 1, 1)
