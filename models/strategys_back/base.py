from odoo import api, fields, models, exceptions


class BaseStrategy(models.Model):
    _inherit = 'fo.trading.strategy.trading'
    _description = "策略交易基础方法"

    def get_exchange_all(self, exchange=None):
        """
        获取交易所所有对象
        m, u, o, c, kd, exchange= self.get_exchange_all()
        :return:
        """
        if not exchange:
            exchange = self.exchange_id.get_exchange()
        symbol = self.symbol_id.name
        m = exchange.market(symbol)
        u = exchange.user(symbol)
        o = exchange.order(symbol)
        c = exchange.compute(symbol)
        kd = exchange.kdata(symbol)
        return m, u, o, c, kd, exchange

    def get_buy_amount(self, exchange, max_k_num=20, stop_loss_price=None, entry_price=None):
        """
        获取购买的amount
        :param exchange:
        :param max_k_num:
        :param stop_loss_price:
        :param entry_price:
        :return:
        """
        # 获取交易所对象
        m, u, o, c, kd, exchange = self.get_exchange_all(exchange)
        kd.update_kdata(self.timeframe, max_k_num + 5)
        # 获取stop_loss_price
        if not stop_loss_price:
            if self.side == 'long':
                stop_loss_price = kd.get_kdata_min_price(self.timeframe, 0, max_k_num)
                stop_loss_price = stop_loss_price * (1 - 0.0005)
            elif self.side == 'short':
                stop_loss_price = kd.get_kdata_max_price(self.timeframe, 0, max_k_num)
                stop_loss_price = stop_loss_price * (1 + 0.0005)

        # 获取入场价格
        if not entry_price:
            entry_price = m.get_now_price()
        # 获取需要购买的amount
        need_buy_amount = c.get_buy_amount_for_stop_price(self.side,
                                                          stop_loss_price,
                                                          self.max_loss,
                                                          entry_price)
        if need_buy_amount:
            return need_buy_amount, stop_loss_price
        return False

    def is_new_k(self, kd):
        """
        判断是否是新的k先
        :param kd:
        :return:
        """
        last_o = kd.get_open(self.timeframe, 1)
        last_c = kd.get_close(self.timeframe, 1)
        last_h = kd.get_high(self.timeframe, 1)
        last_l = kd.get_low(self.timeframe, 1)
        if self.last_o != last_o and self.last_c != last_c and self.last_h != last_h and self.last_l != last_l:
            self.last_o = last_o
            self.last_l = last_l
            self.last_c = last_c
            self.last_h = last_h
            return True

        return False

    def strategy_run(self):
        """
        策略运行核心
        1. 初始化选择策略
        2. 运行策略
        3. 策略结束扫尾
        :return:
        """
        # 1. 判断策略状态，是否需要进行交易
        if self.strategy_type == 'double_ema':
            self.double_ema_start()
        elif self.strategy_type == "sky_city":
            self.sky_city_start()
