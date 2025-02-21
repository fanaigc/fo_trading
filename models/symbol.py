from odoo import api, fields, models


class Symbol(models.Model):
    _name = 'fo.trading.symbol'
    _description = "币种"

    name = fields.Char("名称", required=True)
