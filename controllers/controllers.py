# -*- coding: utf-8 -*-
# from odoo import http


# class FoTrading(http.Controller):
#     @http.route('/fo_trading/fo_trading', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/fo_trading/fo_trading/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('fo_trading.listing', {
#             'root': '/fo_trading/fo_trading',
#             'objects': http.request.env['fo_trading.fo_trading'].search([]),
#         })

#     @http.route('/fo_trading/fo_trading/objects/<model("fo_trading.fo_trading"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('fo_trading.object', {
#             'object': obj
#         })

