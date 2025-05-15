from odoo import api, fields, models, exceptions


class DoubleEMAStrategy(models.Model):
    _inherit = 'fo.trading.strategy.trading'
    _description = "双均线策略"

    # double_ema参数
    double_ema_fast_num = fields.Integer("EMA快线", default=10)
    double_ema_slow_num = fields.Integer("EMA慢线", default=20)
    double_ema_stop_loss_max_k_num = fields.Integer("止损最大K数", default=10)

    def double_ema_start(self):
        """
        双均线程序启动
        1. 判断当前是否有运行中的订单
        2. 有订单运行
        3. 无订单入场
        :return:
        """
        instance = self.trading_ids.filtered_domain([('is_now_trading', '=', True)])
        if instance:
            self.double_ema_has_position(instance)
        else:
            self.double_ema_not_has_position()

    def double_ema_sub_create(self, **kwargs):
        """
        创建子订单
        # 1. 判断是否存在已经拥有的仓位信息
        # 2. 初始化子订单信息
        # 3. 创建子订单
        :param kwargs:
        :return:
        """
        # 1. 判断是否存在已经拥有的仓位信息
        u = kwargs.get('u')  # 获取exchange.u
        if not u:
            raise exceptions.ValidationError("double_ema_sub_create缺少交易所对象u")
        entry_price = u.get_position_avg_buy_price(self.side)
        if not entry_price:
            return False

        # 创建Name的名称
        name = "{}-{}".format(self.name, len(self.trading_ids) + 1)

        for instance in self.trading_ids.filtered_domain([('is_now_trading', '=', True)]):
            instance.is_now_trading = False

        self.trading_ids.create({
            'name': name,
            "side": self.side,
            'entry_price': entry_price,
            'is_now_trading': True,
            'trading_id': self.id
        })

    def double_ema_has_position(self, instance):
        """
        有仓位运行
        1. 初始化交易所对象
        2. 交易所判断是否有仓位
        3. 判断前根K线是否满足卖出条件
        :param instance: 子订单对象
        :return:
        """
        # 1. 初始化交易所对象
        m, u, o, c, kd, exchange = self.get_exchange_all()
        kd.update_kdata(self.timeframe, 10)
        # 只有是新K线才执行代码
        if not self.is_new_k(kd):
            return
        # 2. 判断当前仓位是否还存在
        now_amount = u.get_position_amount(self.side)
        if not now_amount:
            instance.is_now_trading = False
            return

        # 3. 判断前根K线是否满足卖出条件
        fast_price = kd.get_ema(self.timeframe, self.double_ema_fast_num, 1)
        slow_price = kd.get_ema(self.timeframe, self.double_ema_slow_num, 1)

        if self.side == 'long' and fast_price < slow_price:
            # 多头， 快线下穿慢线进行卖出操作
            o.close_order(self.side, now_amount)
        elif self.side == 'short' and fast_price > slow_price:
            # 空头，快线上穿慢线
            o.close_order(self.side, now_amount)

    def double_ema_not_has_position(self):
        """
        无仓位运行
        1. 初始化交易所对象
        2. 程序判断是否拥有仓位
        3. 判断前根K线是否满足开仓条件
        :return:
        """
        # 1. 初始化交易所对象
        m, u, o, c, kd, exchange = self.get_exchange_all()
        kd.update_kdata(self.timeframe, 10)
        # 只有是新K线才执行代码
        if not self.is_new_k(kd):
            return

        # 2. 程序判断是否拥有仓位
        now_amount = u.get_position_amount(self.side)
        if now_amount:
            self.double_ema_sub_create(u=u)
            # 进行一次挂止损单的操作
            return

        # 3. 判断前根K线是否满足卖出条件
        fast_price = kd.get_ema(self.timeframe, self.double_ema_fast_num, 1)
        slow_price = kd.get_ema(self.timeframe, self.double_ema_slow_num, 1)

        stop_loss_price = 0
        if self.side == 'long' and fast_price > slow_price:
            # 多头， 快线下穿慢线进行卖出操作
            need_buy_amount, stop_loss_price = self.get_buy_amount(exchange,
                                                                   max_k_num=self.double_ema_stop_loss_max_k_num)
            if not need_buy_amount:
                print("做多：当前无法计算出需要购买的amount")
                return
            o.open_order(self.side, need_buy_amount)
        elif self.side == 'short' and fast_price < slow_price:
            # 空头，快线上穿慢线
            need_buy_amount, stop_loss_price = self.get_buy_amount(exchange,
                                                                   max_k_num=self.double_ema_stop_loss_max_k_num)
            if not need_buy_amount:
                print("做空：当前无法计算出需要购买的amount")
                return
            o.open_order(self.side, need_buy_amount)

        # 3. 进行止损
        if stop_loss_price:
            now_amount = u.get_position_amount(self.side)
            if now_amount:
                o.stop_order_for_price(self.side, stop_loss_price)

# class Strategy(object):
#     def __init__(self, exchange):
#         self.exchange = exchange
#         self.side = exchange.side
#         self.timestamp = exchange.timestamp
#         self.max_stop_loss = exchange.max_stop_loss
#         self.fast_num = exchange.double_ema_fast_num
#         self.slow_num = exchange.double_ema_slow_num
#         self.stop_loss_max_k_num = exchange.double_ema_stop_loss_max_k_num
#
#     def start(self):
#         """
#         量化程序开始
#         :return:
#         """
#         pass
