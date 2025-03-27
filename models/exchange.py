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
