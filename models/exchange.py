import os.path

from odoo import api, fields, models, exceptions
import ccxt
from ..apis import CcxtApis
import json


class Exchange(models.Model):
    _name = 'fo.trading.exchange'
    _description = "交易所配置"

    name = fields.Char("交易所名称")
    exchange_type = fields.Selection([('binance', 'binance'), ('gate', 'gate')],
                                     default='binance', string="交易所类型")

    api_key = fields.Char("API Key")
    api_secret = fields.Char("API Secret")
    is_default = fields.Boolean("默认交易所", default=False)
    timeframe = fields.Selection([('1m', '1分钟'), ('5m', '5分钟'), ('15m', '15分钟'),
                                  ('30m', '30分钟'), ('1h', '1小时'), ('4h', '4小时'),
                                  ('1d', '天线'), ('1w', '周线')], string='偏好周期', default='5m', required=True)

    # open_max_loss_rate = fields.Float("开仓最大亏损比例%", default=1)
    #
    # add_max_loss_rate = fields.Float("加仓最大亏损比例%", default=0.5)

    max_loss_rate_for_every = fields.Float("每次购买最大亏损比例%", default=1)
    max_loss_rate_for_position = fields.Float("单仓位最大亏损比例%", default=2)

    def test(self):
        self.get_symbol_max_loss("BTC/USDT:USDT")

    def get_symbol_max_loss(self, symbol, exchange=None, order_rate=None):
        """
        获取symbol可以的最大亏损金额
        1. 先获取exchange对象
        2. 获取仓位信息
        3. 计算出当前可以亏损的金额
        :param symbol:
        :param order_rate: 订单的比率，没有值就获取默认值
        :param exchange:
        :return:
        """
        # 1. 先获取exchange对象
        if not exchange:
            exchange = self.get_default_exchange()

        if not order_rate:
            order_rate = self.max_loss_rate_for_every

        u = exchange.user(symbol)

        # 2. 计算仓位信息
        # 2.1 计算仓位的余额
        balance = u.get_balance()
        # 2.2 计算已经使用的所有余额
        use_balance = self.env['fo.trading.positions'].get_all_position_max_loss()
        # 2.3 计算当前可以使用的余额
        can_use_balance = balance + use_balance
        # 2.4 判断当前是否存在symbol的仓位
        position_instance = self.env['fo.trading.positions'].search(
            [('state', '=', '1'), ('symbol_id.name', '=', symbol)])

        # 3. 计算出当前可以亏损的金额
        # 3.1 计算加仓的max_loss
        max_loss = can_use_balance * order_rate / 100

        if position_instance:
            # 3.1 已经存在仓位，重新计算can_use_balance
            can_use_balance = can_use_balance + position_instance.max_loss
            # 3.2 计算最大仓位max_loss值
            position_max_loss = can_use_balance * self.max_loss_rate_for_position / 100
            # 3.3 计算position实际亏损和最大亏损的差值
            position_max_loss = position_max_loss + position_instance.now_loss
            # 3.4  max_loss和position_max_loss取最小值
            max_loss = min(max_loss, position_max_loss)

        return max_loss

    def set_default(self):
        """
        设置交易所为默认交易所
        """
        self.ensure_one()
        instances = self.search([('is_default', '=', True)])
        for instance in instances:
            instance.is_default = False
        self.is_default = True

    def _get_exchange(self):
        exchange = CcxtApis(exchange_name=self.exchange_type,
                            api_key=self.api_key,
                            api_secret=self.api_secret)
        return exchange

    def get_exchange(self):
        exchange = self._get_exchange()
        markets, markets_by_id = self.get_markets()
        exchange.exchange.markets = markets
        # exchange.exchange.markets_by_id = markets_by_id
        exchange.exchange.load_markets()
        return exchange

    def get_default_exchange(self):
        """
        获取默认的exchange
        :return:
        """
        instance = self.search([('is_default', '=', True)], limit=1)
        if instance:
            return instance.get_exchange()
        return False

    def test_exchange(self):
        try:
            self.get_exchange()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '成功',
                    'message': "连接成功！",
                    'type': 'success',  # 通知类型: success, warning, danger
                    'sticky': False,  # 是否常驻
                },
            }

        except Exception as e:
            raise exceptions.ValidationError("连接失败！")

    def get_cache_file_path(self, file_name=None):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        father_path = os.path.dirname(current_dir)
        cache_path = os.path.join(father_path, 'apis', 'cache')
        if not file_name:
            name = "markets"
        else:
            name = file_name
        file_name = '{}-{}.json'.format(self.exchange_type, name)

        file_path = os.path.join(cache_path, file_name)
        return file_path

    def get_markets(self):
        """
        获取ccxt中markets文件
        1. 先获取缓存数据
        2. 缓存数据不存在这获取在线的数据
        """
        file_path = self.get_cache_file_path()
        markets = None
        markets_by_id = None
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    markets = json.load(f)
                except Exception as e:
                    pass

        file_path = self.get_cache_file_path("markets_by_id")
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    markets_by_id = json.load(f)
                except Exception as e:
                    pass

        if not all([markets, markets_by_id]):
            return self.update_markets()
        return markets, markets_by_id

    def update_markets(self):
        """
        更新market数据
        """
        exchange = self._get_exchange()
        # 获取market
        markets = exchange.exchange.load_markets()
        file_path = self.get_cache_file_path()
        with open(file_path, 'w') as f:
            json.dump(markets, f)

        # 获取markets_by_id
        markets_by_id = exchange.exchange.set_markets(markets)
        file_path_markets_by_id = self.get_cache_file_path("markets_by_id")
        with open(file_path_markets_by_id, 'w') as f:
            json.dump(markets_by_id, f)

        return markets, markets_by_id
