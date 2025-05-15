from odoo import api, fields, models


class Symbol(models.Model):
    _name = 'fo.trading.symbol'
    _description = "币种"

    name = fields.Char("名称", required=True)

    # 外键字段
    monitor_ids = fields.Many2many('fo.trading.monitor', string="监控器")

    def start_monitor(self, kd):
        for monitor in self.monitor_ids:
            monitor.start(kd)
        # if not exchange:
        #     raise exceptions.ValidationError("请先创建默认交易所")
        #
        # symbol_name = "BTC/USDT:USDT"
