from odoo import api, fields, models, exceptions
import ccxt
from ..apis import CcxtApis


class Exchange(models.Model):
    _name = 'fo.trading.exchange'
    _description = "交易所配置"

    name = fields.Char("交易所名称")
    exchange_type = fields.Selection([('binance', 'binance'), ('gate', 'gate')],
                                     default='binance', string="交易所类型")

    api_key = fields.Char("API Key")
    api_secret = fields.Char("API Secret")

    def get_exchange(self):
        exchange = CcxtApis(exchange_name=self.exchange_type,
                            api_key=self.api_key,
                            api_secret=self.api_secret)
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
