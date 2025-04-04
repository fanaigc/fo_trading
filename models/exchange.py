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

    open_max_loss_rate = fields.Float("开仓最大亏损比例%", default=1)
    add_max_loss_rate = fields.Float("加仓最大亏损比例%", default=0.5)

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
