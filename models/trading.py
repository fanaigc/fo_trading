import logging
import time

from odoo import api, fields, models, exceptions
from datetime import datetime, timedelta


#
# class TradingSub(models.Model):
#     _name = 'fo.trading.trading.sub'
#     _description = "加仓订单"
#
#     state = fields.Selection([('1', '监控中'), ('2', '已完成'), ('-1', "无法交易")], default='1', string="状态")
#     entry_price = fields.Float("入场价格", digits=(16, 9), default=0, help="入场价格，0为市价买入")
#     stop_loss_price = fields.Float("止损价格", digits=(16, 9), help="止损价格，如果不输入默认为20根K线最小值")
#     buy_price = fields.Float("实际买入价格", digits=(16, 9), default=0)
#     max_loss = fields.Float("最大亏损")
#     need_buy_amount = fields.Float("需要买入amount数量")
#     before_amount = fields.Float("加仓前的amount")
#     exchange_order_id = fields.Char("交易ID")
#
#     trading_id = fields.Many2one("fo.trading.trading", "父单", required=True)
#     error_msg = fields.Char("错误说明")
#     add_remark = fields.Html("加仓说明")
#
#     @api.model_create_multi
#     def create(self, vals_list):
#         instances = super().create(vals_list)
#         for instance in instances:
#             instance.stop_loss_price = instance.trading_id.stop_loss_price
#             instance.before_amount = instances.trading_id.now_amount
#             instance.add_corn()
#         return instances
#
#     @api.model
#     def unlink(self):
#         for record in self:
#             if record.state != '1':
#                 raise exceptions.UserError("只有在监控中的加仓记录才能删除！")
#         return super().unlink()
#
#     def add_corn(self):
#         """
#         加仓的核心方法
#         1. 计算加仓最大亏损金额，并写入参数
#         2. 计算需要加仓数量
#         3. 实行加仓操作
#         """
#         # 只有状态为监控中才可以交易
#         if self.state != '1':
#             return
#
#         # 1. 计算最大加仓亏损金额
#         trading_instance = self.trading_id
#         symbol_name = trading_instance.symbol_id.name
#         exchange = trading_instance.exchange_id.get_exchange()
#         c = exchange.compute(symbol_name)
#         m = exchange.market(symbol_name)
#         u = exchange.user(symbol_name)
#         o = exchange.order(symbol_name)
#         side = trading_instance.side
#         if not self.max_loss:
#             # 1.1 获取当前在监控中的所有最大亏损的和
#             all_max_loss_money = 0
#             for instance in self.env['fo.trading.trading'].search([('state', '=', '1')]):
#                 all_max_loss_money += instance.max_loss
#             # 1.2 获取所有balance
#             max_balance = u.get_balance() - all_max_loss_money
#             # 1.3 计算出max_loss
#             self.max_loss = max_balance * trading_instance.exchange_id.add_max_loss_rate / 100
#
#             # 先计算出当前父类的最大亏损金额
#             if trading_instance.is_has_position:
#                 max_loss = u.get_appoint_stop_loss_max_loss(trading_instance.side, self.stop_loss_price)
#             else:
#                 max_loss = trading_instance.max_loss
#             # 计算出当前max_loss
#             now_max_loss = max_loss + self.max_loss
#             # 取当前计算出来的最大亏损和父类已经存在的最大亏损取最大值为实际的最大亏损
#             trading_instance.max_loss = max(now_max_loss, trading_instance.max_loss)
#
#         # 2. 计算需要加仓数量
#         if not self.need_buy_amount:
#             entry_price = self.entry_price
#             if not self.entry_price:
#                 entry_price = m.get_now_price()
#             self.need_buy_amount = c.get_buy_amount_for_stop_price(trading_instance.side,
#                                                                    self.stop_loss_price,
#                                                                    self.max_loss,
#                                                                    entry_price)
#         # 2.1 如果还是没有需要购买的amount，则退出交易
#         if not self.need_buy_amount:
#             self.state = '-1'
#             self.error_msg = '无法计算出买入仓位！'
#             return
#
#         # 3. 实行加仓操作
#         need_buy_amount = self.need_buy_amount
#         # 3.1 市价买入的操作
#         if self.entry_price == 0:
#             logging.info("{} - 准备市价买入：{}".format(symbol_name, need_buy_amount))
#             try:
#                 order_info = o.open_order(side, need_buy_amount, log=True)
#                 self.exchange_order_id = order_info['id']
#
#             except Exception as e:
#                 self.state = '-1'
#                 self.error_msg = '市价买入失败！异常值：{}'.format(e)
#                 logging.error(self.error_msg)
#
#             buy_price = u.get_position_avg_buy_price(side)
#             if not buy_price:
#                 self.state = '-1'
#                 self.error_msg = '市价买入后，还是没有仓位'
#                 logging.error(self.error_msg)
#
#             self.state = '2'
#             self.buy_price = buy_price
#             return
#         # 3.2 限价买入的操作
#         # 3.2.1 有订单，则判断订单是否成交
#         if self.exchange_order_id:
#             # 判断交易订单是否已经结束
#             if not o.order_is_closed(self.exchange_order_id):
#                 return
#             # 交易完成后计算最大亏损额度
#             max_loss = c.get_max_loss(side, self.stop_loss_price)
#             if max_loss > trading_instance.max_loss:
#                 trading_instance.max_loss = max_loss
#
#             # 交易结束后进行赋值
#             self.buy_price = self.entry_price
#             self.state = '2'
#             return
#
#         # 3.2.2 没有订单，则进行挂单
#         logging.info("{} - 准备限价：{}, 买入：{}".format(symbol_name, self.entry_price, need_buy_amount))
#
#         try:
#             order_info = o.open_order(side, need_buy_amount, self.entry_price, log=True)
#             self.exchange_order_id = o.get_order_id(order_info)
#         except Exception as e:
#             self.state = '2'
#             self.error_msg = '限价单买入失败！异常值：{}'.format(e)
#             logging.error(self.error_msg)
#

#
#     entry_price = fields.Float("入场价格", digits=(16, 9), default=0, help="入场价格，0为市价买入", required=True,
#                                tracking=True)
#     buy_price = fields.Float("实际买入价格", digits=(16, 9), default=0,
#                              tracking=True)
#     stop_loss_price = fields.Float("止损价格", digits=(16, 9), required=True,
#                                    help="止损价格，如果不输入默认为20根K线最小值", tracking=True)
#     stop_win_price = fields.Float("止盈价格", digits=(16, 9), help="如果没有止盈价格，则动态止盈", tracking=True)
#     side = fields.Selection([('long', "做多"), ('short', "做空")], string="方向", required=True)
#     now_amount = fields.Float("当前的amount")
#     max_loss = fields.Float("最大亏损", tracking=True)
#     timeframe = fields.Selection([
#         ('1m', '1分钟'), ('5m', '5分钟'), ('15m', '15分钟'),
#         ('30m', '30分钟'), ('1h', '1小时'), ('4h', '4小时'),
#         ('1d', '天线'), ('1w', '周线')], string='参考周期')
#
#     open_remark = fields.Html("开仓说明")
#     close_remark = fields.Html("平仓总结")
#     pnl = fields.Float("收益额", digits=(16, 3))
#     pnl_fee = fields.Float("手续费", digits=(16, 3))
#     is_has_position = fields.Boolean("是否拥有过仓位", default=False)
#     exchange_order_id = fields.Char("交易所订单ID")
#     error_msg = fields.Char("错误信息")
#     open_time = fields.Char("开仓时间", help='开仓时间可以帮助进行获取收益率')
#
#     @api.depends("pnl", "max_loss")
#     def _compute_pnl_rate(self):
#         """
#         自动计算收益率
#         """
#         for record in self:
#             if record.max_loss == 0:
#                 record.pnl_rate = 0
#             else:
#                 record.pnl_rate = record.pnl / record.max_loss
#
#     pnl_rate = fields.Float("盈亏比", store=True, digits=(16, 3), help="针对最大亏损计算比例",
#                             compute=_compute_pnl_rate)
#
#     # 外键字段
#     symbol_id = fields.Many2one("fo.trading.symbol", string="币种", required=True)
#     exchange_id = fields.Many2one("fo.trading.exchange", string="交易所")
#     trading_sub_ids = fields.One2many('fo.trading.trading.sub', 'trading_id', string="加仓订单")
#
#     # exchange_type = fields.Selection([('binance', 'binance'), ('gate', 'gate')],
#     #                                  default='binance', string="交易所类型")
#     #
#     # api_key = fields.Char("API Key")
#     # api_secret = fields.Char("API Secret")
#
#
# class TradingButton(models.Model):
#     _inherit = 'fo.trading.trading'
#
#     def _cron(self):
#         """
#         定时任务
#         """
#         # 查询所有正在运行中的订单
#         instance = self.search([('state', '=', '1')], limit=1)
#         if instance:
#             # 按顺序执行核心
#             instance.core()
#
#             # 核心执行完毕后，执行加仓操作
#             for sub_instance in instance.trading_sub_ids:
#                 sub_instance.add_corn()
#
#     def set_default_exchange(self):
#         """
#         设置默认交易所
#         """
#         instance = self.exchange_id.search([('is_default', '=', True)], limit=1)
#         if not instance:
#             raise exceptions.ValidationError("请先设置默认交易所在进行交易！！")
#         self.exchange_id = instance.id
#
#     def set_max_loss(self, exchange):
#         """
#         设置最大亏损金额
#         1. 获取当前所有余额
#         2. 计算1%来作为最大亏损金额进行赋值
#         """
#         # 1.1 获取当前在监控中的所有最大亏损的和
#         all_max_loss_money = 0
#         for instance in self.env['fo.trading.trading'].search([('state', '=', '1')]):
#             all_max_loss_money += instance.max_loss
#
#         # 1.2 获取所有balance
#         u = exchange.user(self.symbol_id.name)
#         max_balance = u.get_balance() - all_max_loss_money
#
#         # 2. 获取配置的最大亏损百分比
#         self.max_loss = max_balance * self.exchange_id.open_max_loss_rate / 100
#
#     def check_args(self):
#         """
#         校验参数
#         1. 检查是否存在可以交易的仓位
#         2. 查看盈亏比是否有1：1，否则不可以进行交易
#         """
#         # 判断一下是否已经存在当前币种正在交易的订单，存在则不允许校验通过
#         instance = self.search([('state', '=', '1'), ('symbol_id', '=', self.symbol_id.id)], limit=1)
#         if instance:
#             raise exceptions.ValidationError(
#                 "当前币种：{}，已经存在正在交易的订单，不允许重复创建！".format(self.symbol_id.name))
#         self.set_default_exchange()
#         exchange = self.exchange_id.get_exchange()
#         self.set_max_loss(exchange)
#         symbol_name = self.symbol_id.name
#         c = exchange.compute(symbol_name)
#         m = exchange.market(symbol_name)
#         # u = exchange.user(symbol_name)
#
#         now_price = m.get_now_price()
#         entry_price = self.entry_price
#         if not self.entry_price:
#             entry_price = now_price
#
#         # 1. 检查是否存在可以交易的仓位
#         need_buy_amount = c.get_buy_amount_for_stop_price(self.side,
#                                                           self.stop_loss_price,
#                                                           self.max_loss,
#                                                           entry_price)
#         if not need_buy_amount:
#             raise exceptions.ValidationError("当前止损价格和入场价格无法计算出最小仓位！")
#         # 2. 查看盈亏比是否有1：1，否则不可以进行交易
#         ykb = 0
#         syl = 0
#         if self.stop_win_price:
#             if self.side == 'long':
#                 ykb = (self.stop_win_price - entry_price) / (entry_price - self.stop_loss_price)
#                 syl = (self.stop_win_price - entry_price) / entry_price
#             elif self.side == 'short':
#                 ykb = (entry_price - self.stop_win_price) / (self.stop_loss_price - entry_price)
#                 syl = (entry_price - self.stop_win_price) / entry_price
#
#             # 盈亏比小于1不交易
#             if ykb < 1:
#                 raise exceptions.ValidationError("盈亏比小于1不适合交易！")
#
#             if syl < 0.005:
#                 raise exceptions.ValidationError("收益率0.5%都没有就别做交易了!!")
#         level = min(c.get_max_lever(entry_price, self.stop_loss_price), m.max_level)
#         m.set_level(level)
#         self.state = '0'
#
#     def back_check(self):
#         """
#         回退状态
#         """
#         self.state = '-1'
#         self.name = self._default_name()
#
#         # 删除所有的加仓记录
#         for instance in self.trading_sub_ids:
#             instance.unlink()
#
#         # 取消所有挂单
#         exchange = self.exchange_id.get_exchange()
#         o = exchange.order(self.symbol_id.name)
#         o.cancel_open_order(self.side)
#         o.cancel_close_order(self.side)
#
#     def start(self):
#         """
#         程序启动
#         """
#         self.state = '1'
#         self.core()
#
#     def add(self):
#         """
#         执行加仓操作
#         1. 判断当前是否可以进行加仓
#         2. 弹出加仓form图表
#         """
#         # 1. 判断当前是否可以进行加仓
#         instances = self.trading_sub_ids
#         can_add = True
#         for instance in instances:
#             if instance.state == '1':
#                 can_add = False
#                 break
#         if not can_add:
#             raise exceptions.ValidationError("当前还有为加仓成功的订单，不可以进行加仓！")
#
#         # 2. 弹出form图表
#         return {
#             'name': "加仓",
#             'type': "ir.actions.act_window",
#             'res_model': 'fo.trading.trading.sub',
#             'view_mode': 'form',
#             'target': 'new',
#             'context': {
#                 'default_trading_id': self.id
#             }
#         }
#
#     def stop(self):
#         """
#         程序停止
#         """
#         exchange = self.exchange_id.get_exchange()
#         o = exchange.order(self.symbol_id.name)
#         u = exchange.user(self.symbol_id.name)
#         # 先清仓00
#         now_amount = u.get_position_amount(self.side)
#         if now_amount:
#             # 先执行一个平仓
#             o.close_order(self.side, now_amount)
#             # 在计算一下这一单的收益情况
#             self.core_has_position(exchange)
#
#         # 取消所有挂单
#         o.cancel_open_order(self.side)
#         o.cancel_close_order(self.side)
#
#         self.state = '2'
#
#     def core(self):
#         """
#         量化核心代码，需要先初始化交易所对象
#         1. 检查是否拥有过仓位
#         2. 没有仓位 - 监控买入
#         3. 有仓位 - 监控是否平仓
#         """
#         exchange = self.exchange_id.get_exchange()
#
#         if self.is_has_position:
#             self.core_has_position(exchange)
#         else:
#             self.core_not_position(exchange)
#
#     def core_not_position(self, exchange):
#         """
#         监控买入逻辑
#         1. 判断是否有仓位
#         2. 无仓位 进行挂单
#             1. 计算需要买入的仓位价值
#             2. 入场价格为0，直接买入
#             3. 有入场价格，判断是否挂单
#             4. 进行挂单操作
#         3. 有仓位 修改仓位状态
#         """
#         symbol_name = self.symbol_id.name
#         m = exchange.market(symbol_name)
#         u = exchange.user(symbol_name)
#         o = exchange.order(symbol_name)
#         kd = exchange.kdata(symbol_name)
#         c = exchange.compute(symbol_name)
#
#         now_value = u.get_position_value(side=self.side)
#         # 有仓位 修改仓位状态
#         if now_value:
#             self.is_has_position = True
#             self.open_time = u.get_open_time(self.side)
#             return
#
#         # 无仓位 进行挂单
#         # 1. 计算需要买入的仓位价值
#         need_buy_amount = c.get_buy_amount_for_stop_price(self.side,
#                                                           self.stop_loss_price,
#                                                           self.max_loss,
#                                                           self.entry_price)
#         if not need_buy_amount:
#             self.state = '2'
#             logging.error("未计算出可以购买的仓位，不进行购买！")
#             return
#
#         # 2. 判断一下entry_price是否为0，是否选择市价直接买进
#         if self.entry_price == 0:
#             logging.info("{} - 准备市价买入：{}".format(symbol_name, need_buy_amount))
#             try:
#                 order_info = o.open_order(self.side, need_buy_amount, log=True)
#                 self.exchange_order_id = order_info['id']
#
#             except Exception as e:
#                 self.state = '2'
#                 self.error_msg = '市价买入失败！异常值：{}'.format(e)
#                 logging.error(self.error_msg)
#
#             buy_price = u.get_position_avg_buy_price(self.side)
#             if not buy_price:
#                 self.state = '2'
#                 self.error_msg = '市价买入后，还是没有仓位'
#                 logging.error(self.error_msg)
#
#             self.is_has_position = True
#             self.buy_price = buy_price
#             return
#
#         # 3. 限价进行买入
#         # 先检查一下订单号是否已经成交
#         # if self.exchange_order_id:
#         #     state = o.get_order_info_status(self.exchange_order_id)
#         #     # 判断状态是否已经成交
#         #     if state == 1:
#         #         # 已经成功买入
#         #         self.is_has_position = True
#         #         self.buy_price = self.entry_price
#         #         return
#
#         # 3.1 先查看entry_price已经挂单的amount
#         amount = o.get_open_order_amount(self.side, self.entry_price)
#         need_buy_amount = need_buy_amount - amount
#         if need_buy_amount > 0:
#             logging.info("{} - 准备限价：{}, 买入：{}".format(symbol_name, self.entry_price, need_buy_amount))
#
#             try:
#                 order_info = o.open_order(self.side, need_buy_amount, self.entry_price, log=True)
#                 self.exchange_order_id = o.get_order_id(order_info)
#             except Exception as e:
#                 self.state = '2'
#                 self.error_msg = '限价单买入失败！异常值：{}'.format(e)
#                 logging.error(self.error_msg)
#
#     def core_has_position(self, exchange):
#         """
#         监控平仓逻辑
#         1. 查看当前仓位是否存在
#         2. 不存在则更新订单状态
#         3. 存在则进行挂止损和止盈单
#         """
#         symbol_name = self.symbol_id.name
#         m = exchange.market(symbol_name)
#         u = exchange.user(symbol_name)
#         o = exchange.order(symbol_name)
#         kd = exchange.kdata(symbol_name)
#         c = exchange.compute(symbol_name)
#         now_amount = u.get_position_amount(self.side)
#         self.now_amount = now_amount
#
#         # 不存在则更新订单状态， 结束所有程序运行
#         if not now_amount:
#             # 循环10次，防止出现仓位存在提前退出的情况
#             for i in range(10):
#                 now_amount = u.get_position_amount(self.side)
#                 if now_amount:
#                     return
#                 time.sleep(1)
#             self.state = '2'
#             # 计算收益
#             info = u.get_open_time_pnl_info(self.side, self.open_time)
#             # info = o.get_last_close_order_info()
#             self.pnl = info['pnl']
#             self.pnl_fee = info['pnl_fee']
#             return
#
#         # 更新止损
#         o.stop_order_for_price(self.side, self.stop_loss_price)
#
#         # 更新止盈
#         if not self.stop_win_price:
#             return
#         now_close_amount = o.get_close_order_amount(self.side, self.stop_win_price)
#         # 如果在对应价位没有挂单止盈，说明止盈价格已经改动，取消所有挂单重新进行挂单
#         if not now_close_amount:
#             o.cancel_close_order(self.side, log=True)
#         need_close_amount = now_amount - now_close_amount
#         if need_close_amount:
#             o.close_order(self.side, need_close_amount, self.stop_win_price, log=True)


def get_now_datetime():
    """
    获取当前的时间
    """
    return datetime.now() + timedelta(hours=8)
    # return datetime.now()


class Trading(models.Model):
    _name = 'fo.trading.trading'
    _description = "交易指令"

    def _default_name(self):
        """
        生成默认名称
        """
        now_time = get_now_datetime()
        now_time_str = now_time.strftime("%Y%m%d")
        trading_num = self.search_count([('create_year', '=', now_time.year),
                                         ('create_month', '=', now_time.month),
                                         ('create_day', '=', now_time.day)])
        name = 'T{}-{}'.format(now_time_str, trading_num + 1)
        return name

    @api.onchange('stop_win_condition')
    def _onchange_stop_win_condition(self):
        """
        当止盈条件改变时，自动更新止盈参数
        :return:
        """
        if self.stop_win_condition:
            self.stop_win_args = self.stop_win_condition.args

    @api.onchange('stop_loss_condition')
    def _onchange_stop_loss_condition(self):
        """
        当止损条件改变时，自动更新止损参数
        :return:
        """
        if self.stop_loss_condition:
            self.stop_loss_args = self.stop_loss_condition.args

    @api.onchange('execute_condition')
    def _onchange_execute_condition(self):
        """
        当执行条件改变时，自动更新执行参数
        :return:
        """
        if self.execute_condition:
            self.execute_args = self.execute_condition.args

    def _default_exchange(self):
        """
        获取默认交易所
        :return:
        """
        instance = self.env['fo.trading.exchange'].search([('is_default', '=', True)], limit=1)
        return instance.id

    name = fields.Char("交易编号", default=_default_name)
    symbol_id = fields.Many2one("fo.trading.symbol", string="交易对", required=True)

    def _default_timeframe(self):
        """
        获取偏好周期
        :return:
        """
        instance = self.env['fo.trading.exchange'].search([('is_default', '=', True)], limit=1)
        if not instance:
            return "15m"
        return instance.timeframe

    timeframe = fields.Selection([('1m', '1分钟'), ('5m', '5分钟'), ('15m', '15分钟'),
                                  ('30m', '30分钟'), ('1h', '1小时'), ('4h', '4小时'),
                                  ('1d', '天线'), ('1w', '周线')], string='时间周期', default=_default_timeframe,
                                 required=True)
    mode = fields.Selection([('open', "开仓"), ('close', "平仓(未实现)")], string="交易模式",
                            default='open', required=True)
    side = fields.Selection([('long', "多头"), ('short', "空头")], string="方向", required=True)

    state = fields.Selection([('-1', '编辑中'), ('1', '执行中'), ("2", "已结束")],
                             default='-1',
                             string="状态")
    pnl_rate = fields.Float("盈亏比", store=True, digits=(16, 3), default=2, help="针对最大亏损计算比例")

    every_loss_rate = fields.Float("每次亏损%", default=1, help="每次开仓最多亏损百分比")

    max_execute_num = fields.Integer('最大执行次数', default=1)
    now_execute_num = fields.Integer("已执行次数", default=0)

    create_year = fields.Integer('年', default=lambda x: get_now_datetime().year)
    create_month = fields.Integer('月', default=lambda x: get_now_datetime().month)
    create_day = fields.Integer('日', default=lambda x: get_now_datetime().day)

    # 入场相关
    execute_mode = fields.Selection([('1', "智能计算"), ('2', "指定条件"), ('3', "市价执行")],
                                    string="执行模式", default='1', required=True)
    execute_condition = fields.Many2one("fo.trading.condition", "执行价格")
    execute_args = fields.Char('执行参数')
    # execute_order_id = fields.Char("执行订单ID", help="逻辑判断使用")
    # now_execute_order_id = fields.Many2one('fo.trading.trading.order', "执行订单ID", help="逻辑判断使用")
    now_execute_price = fields.Float("当前执行价格", help="逻辑判断使用")

    # 止盈相关
    stop_win_mode = fields.Selection([('1', "智能计算"), ('2', "指定条件"), ('3', "不止盈")], string="止盈模式",
                                     default='1', required=True)
    stop_win_condition = fields.Many2one("fo.trading.condition", "止盈价格")
    stop_win_args = fields.Char("止盈参数")
    # stop_win_order_id = fields.Char("止盈订单ID")
    now_stop_win_price = fields.Float("当前止盈价格", help="逻辑判断使用")

    # 止损相关
    stop_loss_mode = fields.Selection([('1', "智能计算"), ('2', "指定条件")], string="止损模式", default='1',
                                      required=True)
    stop_loss_condition = fields.Many2one("fo.trading.condition", "止损价格")
    stop_loss_args = fields.Char("止损参数")
    # stop_loss_order_id = fields.Char("止损订单ID")
    now_stop_loss_price = fields.Float("当前止损价格", help="逻辑判断使用")

    # 其他内容
    error_msg = fields.Char("错误信息")

    exchange_id = fields.Many2one("fo.trading.exchange", string="交易所", default=_default_exchange)

    # 订单列表
    order_ids = fields.One2many('fo.trading.trading.order', 'trading_id')

    def t(self):
        # print(123)
        # symbol = self.symbol_id.name
        # o = exchange.order(symbol)
        # o.update_order_price_for_id("36028800701746031", price=93000)
        # self.state = '1'
        # self.run()
        exchange = self.exchange_id.get_exchange()
        self.env['fo.trading.trading.order'].auto_create_order_instance_for_order_list(exchange=exchange)

    def get_compute_price_data(self, exchange, kd, position_instance):
        """
        获取执行价格和止损止盈价格
        第一次获取，直接获取3个值，不加任何高级计算
        # 1. 设置默认价格
        # 2. 获取止损价格
        # 3. 获取止盈价格
        # 4. 获取执行价格
        :param exchange:
        :param kd:
        :param position_instance:
        :return:
        """
        c = exchange.compute(self.symbol_id.name)
        # 1. 设置默认价格
        execute_price = 0
        stop_loss_price = 0
        stop_win_price = 0
        # 2. 获取止损价格
        if self.stop_loss_mode == '2':
            stop_loss_price = self.stop_loss_condition.get_value(kd, self.stop_loss_args)[-1]

        # 3. 获取止盈价格
        if self.stop_win_mode == '2':
            stop_win_price = self.stop_win_condition.get_value(kd, self.stop_win_args)[-1]
        elif self.stop_win_mode == '3':
            stop_win_price = -1

        # 4. 获取执行价格
        if self.execute_mode == '2':
            execute_price = self.execute_condition.get_value(kd, self.execute_args)[-1]
        elif self.execute_mode == '3':
            execute_price = kd.m.get_now_price()

        # 5. 更新一下仓位的止损价格
        price_data = {
            'execute_price': execute_price,
            'stop_loss_price': stop_loss_price,
            'stop_win_price': stop_win_price
        }
        c.update_execute_stop_price(self.side, price_data, stop_loss_price=position_instance.stop_loss_price)
        return price_data

    def get_execute_amount(self, exchange, execute_price, stop_loss_price):
        """
        获取执行的amount

        :param exchange:
        :param execute_price:
        :param stop_loss_price:
        :return:
        """
        c = exchange.compute(self.symbol_id.name)
        max_loss = self.exchange_id.get_symbol_max_loss(symbol=self.symbol_id.name, exchange=exchange)
        if not max_loss:
            return 0
        # 计算出当前最大亏损金额
        need_buy_amount = c.get_buy_amount_for_stop_price(self.side,
                                                          stop_loss_price,
                                                          max_loss,
                                                          execute_price)
        if need_buy_amount:
            return need_buy_amount
        return 0

    def update_now_price_data(self, exchange):
        """
        计算当前的价格，并存储到价格中
        1. 直接计算获取price_data
        2. 智能和优化每个具体的price
        :return:
        """
        # 获取交易所对象
        kd = exchange.kdata(self.symbol_id.name)
        c = exchange.compute(self.symbol_id.name)
        position_instance = self.env['fo.trading.positions'].search([('state', '=', '1'), ('side', '=', self.side),
                                                                     ('symbol_id', '=', self.symbol_id.id)])
        price_data = self.get_compute_price_data(exchange, kd, position_instance)

        # 智能更新和优化每个price的价格
        # 智能更新止损价格 - 止损价格优先计算
        # 1. 非智能计算，不需要获取止损的价格
        if self.stop_loss_mode == '1':
            c.smart_update_stop_loss_price(self.side, price_data, self.timeframe, kd, self.pnl_rate)
        #  智能更新执行价格 - 执行价格第二个计算
        if self.execute_mode == '1':
            c.smart_update_execute_price(self.side, price_data, self.timeframe, kd, self.pnl_rate)
        #  智能更新止盈价格 - 如果需要智能计算止盈，前面两个数据必然会计算出来
        if self.stop_win_mode == '1':
            c.smart_update_stop_win_price(self.side, price_data, self.timeframe, kd, self.pnl_rate)
        return price_data

    def run(self):
        """
        执行操作，必须是执行中且已执行次数小于最大执行次数才进行运行
        :return:
        """
        # 判断是否需要结束
        if self.state != '1':
            return

        # 判断循环是否已经超过最大次数
        if self.now_execute_num >= self.max_execute_num:
            self.state = '2'
            return

        # 判断exchange
        exchange = self.exchange_id.get_exchange()
        if not exchange:
            self.state = '2'
            self.error_msg = "没有交易所对象！"
            return

        # 根据有没有当前执行订单来进行不同的操作
        instances = self.order_ids.filtered_domain([("state", '=', 'open')])
        order_num = len(instances)
        # 假设筛选出来多个数据则，直接删除所有数据
        if order_num > 1:
            for instance in instances:
                instance.unlink()
            return
        elif order_num == 1:
            has_order_instance = True
        else:
            has_order_instance = False

        if not has_order_instance:
            self.run_create_order_instance(exchange)
        else:
            self.run_has_order_instance(exchange, instances)

    def init_run(self):
        """
        初始化运行
        :return:
        """
        self.now_execute_amount = 0
        self.now_stop_win_price = 0
        self.now_execute_price = 0
        self.now_stop_loss_price = 0
        self.now_execute_order_id = None

    def run_has_order_instance(self, exchange, instance):
        """
        有instance，针对instance进行处理
        1. 通过order_id来更新本地的instance
        2. 判断instance是否已经结束
        3. 重新获取最新的执行价格和执行数量，如果和上次记录不一样就进行更新

        :param instance 订单对象
        :param exchange 交易所对象
        :return:
        """
        # 更新从exchange更新instance
        instance.update_for_exchange(exchange)

        # 判断instance是否结束
        if instance.state != 'open':
            self.now_execute_num += 1
            # 如果是取消的话，初始化清空所有的相关存储数据
            self.init_run()
            return

        #  重新获取最新执行价格和执行数量，如果和上次记录不一样就进行更新
        price_data = self.update_now_price_data(exchange)
        execute_price = price_data['execute_price']
        stop_loss_price = price_data['stop_loss_price']
        stop_win_price = price_data['stop_win_price']

        # 设置止盈价格
        if stop_win_price > 0 and stop_win_price != self.now_stop_win_price:
            instance.stop_win_price = stop_win_price

        # 设置止损和amount价格
        if stop_loss_price != self.now_stop_loss_price or \
                execute_price != self.now_execute_price:
            amount = self.get_execute_amount(exchange, execute_price, stop_loss_price)
            if amount <= 0:
                self.state = '2'
                self.error_msg = "amount无法正常计算出来：{}，止损价格：{}，止盈价格：{}".format(
                    execute_price, stop_loss_price, stop_win_price)
                return
            instance.stop_loss_price = stop_loss_price
            instance.execute_price = execute_price
            instance.amount = amount

        # 执行指令
        if instance.order_run(exchange):
            self.now_execute_price = execute_price
            self.now_stop_win_price = stop_win_price
            self.now_stop_loss_price = stop_loss_price

    def run_create_order_instance(self, exchange):
        """
        运行创建execute_order
        1. 计算出执行价格和执行数量
        2. 创建订单instance
        :param exchange
        :return:
        """
        # 获取执行价格
        price_data = self.update_now_price_data(exchange)
        execute_price = price_data['execute_price']
        stop_loss_price = price_data['stop_loss_price']
        stop_win_price = price_data['stop_win_price']

        if not all([execute_price, stop_loss_price]):
            self.state = '2'
            self.error_msg = "无正确价格：执行价格：{}，止损价格：{}，止盈价格：{}".format(
                price_data['execute_price'], price_data['stop_loss_price'], price_data['stop_win_price'])
            return

        # 计算出执行价格
        now_amount = self.get_execute_amount(exchange, self.now_execute_price, self.now_stop_loss_price)
        if now_amount <= 0:
            self.state = '2'
            self.error_msg = "amount无法正常计算出来：{}，止损价格：{}，止盈价格：{}".format(
                price_data['execute_price'], price_data['stop_loss_price'], price_data['stop_win_price'])
            return

        instance = self.env['fo.trading.trading.order'].create({
            "name": "{}-{}".format(self.symbol_id.name, self.now_execute_num + 1),
            "order_type": self.mode,
            'side': self.side,
            "state": "open",
            "execute_price": execute_price if self.execute_mode != '3' else 0,
            "stop_win_price": stop_win_price,
            "stop_loss_price": stop_loss_price,
            "amount": now_amount,
            "trading_id": self.id,
            "symbol_id": self.symbol_id.id,
        })

        # 执行指令
        if instance.order_run(exchange):
            self.now_execute_price = execute_price
            self.now_stop_win_price = stop_win_price
            self.now_stop_loss_price = stop_loss_price


class TradingOrders(models.Model):
    _name = "fo.trading.trading.order"
    _description = "交易订单"

    name = fields.Char("订单名")

    order_type = fields.Selection([("open", "开仓"), ("close", "平仓"), ("stop_loss", "止损"), ("stop_win", "止盈")],
                                  string="模式")

    order_uid = fields.Char("订单ID")
    side = fields.Selection([('long', '多头'), ('short', "空头")], string="方向")
    state = fields.Selection([('open', '挂单中'), ('canceled', "已取消"), ('closed', "已完成")], string="状态")
    execute_type = fields.Selection([('market', '市价执行'), ('limit', "限价执行")])
    price = fields.Float("实际执行价", help="交易所实际的执行价格")
    execute_price = fields.Float("挂单价", help="挂单的入场价格")
    stop_win_price = fields.Float("止盈价")
    stop_loss_price = fields.Float('止损价')

    amount = fields.Float("执行数量", digits=(16, 9))

    create_time = fields.Char("创建时间")
    update_time = fields.Char("最后更新时间")
    trading_id = fields.Many2one("fo.trading.trading", "交易指令")
    symbol_id = fields.Many2one("fo.trading.symbol", "交易对")
    position_id = fields.Many2one("fo.trading.positions", "对应仓位")
    order_loop_num = fields.Integer("交易轮数")
    error_msg = fields.Char("错误描述")

    def update_stop_loss_price(self, exchange, order_info, position_instance):
        """
        获取止损价格
        :return:
        """
        order_uid = order_info['id']
        symbol_name = position_instance.symbol_id.name
        kd = exchange.kdata(symbol_name)
        c = exchange.compute(symbol_name)
        o = exchange.order(symbol_name)
        price = order_info['price']

        exchange_instance = self.env['fo.trading.exchange'].search([('is_default', '=', True)], limit=1)

        timeframe = position_instance.timeframe
        stop_loss_price = position_instance.stop_loss_price
        if not stop_loss_price:
            if order_info['side'] == 'buy':
                side = 'long'
            else:
                side = 'short'

            if len(getattr(kd, 'df_{}'.format(timeframe))) < 100:
                kd.update_kdata(timeframe, 100)

            stop_loss_price = c.compute_stop_loss_price(side, kd, entry_price=price, timeframe=timeframe)
            # #  计算当前ATR值
            # atr = kd.get_atr(timeframe, 14)
            # if order_info['side'] == 'buy':
            #     position_instance.side = 'long'
            #     stop_loss_price = price - atr * 5
            # else:
            #     position_instance.side = 'short'
            #     stop_loss_price = price + atr * 5

        # 计算amount
        max_loss = exchange_instance.get_symbol_max_loss(symbol=symbol_name, exchange=exchange)
        if not max_loss:
            return 0
        # 计算出当前最大亏损金额
        need_buy_amount = c.get_buy_amount_for_stop_price(position_instance.side,
                                                          stop_loss_price,
                                                          max_loss,
                                                          price)
        if not need_buy_amount:
            o.cancel_order_for_id(order_uid)

        # 修改订单的内容
        o.update_order_info_for_id(order_uid, price=price, amount=need_buy_amount)
        return stop_loss_price, need_buy_amount

    def auto_create_order_instance_for_order_list(self, exchange, symbol_name, position_instance):
        """
        自动通过挂单列表创建order_订单

        :param position_instance:
        :param symbol_name:
        :param exchange:
        :return:
        """
        # 获取所有的挂单信息
        order_list = exchange.exchange.fetch_open_orders(symbol_name)
        # o = exchange.order(symbol_name)
        # kd = exchange.kdata(symbol_name)
        c = exchange.compute(symbol_name)
        for order_info in order_list:
            # 如果是API创建额订单则不需要处理
            if order_info['clientOrderId'] == 'api':
                continue

            # 如果是APP创建的订单需要重新设置
            order_uid = order_info['id']
            price = order_info['price']
            is_sell = order_info['reduceOnly']
            instance = self.search([('order_uid', '=', order_uid)], limit=1)
            if is_sell:
                continue
            if not instance:
                # 如果没有instance对象则通过price的价格计算一个新的止损价格，重新挂单
                stop_loss_price, need_buy_amount, = self.update_stop_loss_price(exchange, order_info,
                                                                                position_instance)

                # 创建instance
                self.create({
                    "name": "{}-{}".format(symbol_name, self.order_loop_num + 1),
                    'order_uid': order_uid,
                    "order_type": 'open',
                    'side': position_instance.side,
                    "state": "open",
                    "execute_price": price,
                    "stop_win_price": -1,
                    "stop_loss_price": stop_loss_price,
                    "amount": need_buy_amount,
                    "symbol_id": position_instance.symbol_id.id,
                    'position_id': position_instance.id
                })
                next_time = c.get_next_run_time(fields.Datetime.now(), position_instance.timeframe)
                position_instance.next_execute_time = next_time
                position_instance.last_execute_time = fields.Datetime.now()
            else:
                # 有instance就是更新instance的数据，需要等待执行时间到达之后在执行
                if fields.Datetime.now() < position_instance.next_execute_time:
                    continue
                # 设置一下上次执行时间和下次执行时间
                next_time = c.get_next_run_time(fields.Datetime.now(), position_instance.timeframe)
                position_instance.next_execute_time = next_time
                position_instance.last_execute_time = fields.Datetime.now()
                stop_loss_price, need_buy_amount, = self.update_stop_loss_price(exchange, order_info,
                                                                                position_instance)
                instance.update({
                    "stop_loss_price": stop_loss_price,
                    "amount": need_buy_amount,
                    'position_id': position_instance.id
                })

    def order_run(self, exchange):
        """
        订单运行

        判断是否存在order_uid
        如果存在order_uid
            - 运行has_order_id_run
        如果不存在order_uid
            - 运行create_order_id_run

        :param exchange:
        :return:
        """
        # 进行position_instance的绑定操作
        if not self.position_id:
            position_instance = self.env['fo.trading.positions'].search([("symbol_id", '=', self.symbol_id.id),
                                                                         ('side', '=', self.side),
                                                                         ('state', 'in', ['0', '1'])])
            if not position_instance and self.order_type == 'open':
                # 如果没有仓位，并且是开仓模式，则创建一个仓位
                position_instance = self.env['fo.trading.positions'].create({
                    'symbol_id': self.symbol_id.id,
                    'side': self.side,
                    'timeframe': self.trading_id.timeframe,
                    "state": '0',
                })
            elif not position_instance and self.order_type == 'close':
                # 如果没有仓位，并且是平仓模式，则直接返回
                self.state = 'canceled'
                self.error_msg = "没有仓位，无法进行平仓操作！"
                return
            self.position_id = position_instance.id

        if self.order_uid:
            # 运行has_order_id
            self.has_order_id_run(exchange)
        else:
            # 运行create_order_id
            self.create_order_id_run(exchange)

    def has_order_id_run(self, exchange):
        """
        有order_id的时候运行

        :return:
        """
        # 更新止损价格
        if self.stop_loss_price > 0:
            self.position_id.stop_loss_price = self.stop_loss_price

        # 更新止盈价格
        if self.stop_win_price > 0:
            self.position_id.stop_win_price = self.stop_win_price

        # 更新执行价格和amount数据
        o = exchange.order(self.symbol_id.name)
        o.update_order_info_for_id(self.order_uid, price=self.execute_price, amount=self.amount)
        self.update_for_exchange(exchange)

    def create_order_id_run(self, exchange):
        """
        没有order_id的时候运行

        :param exchange:
        :return:
        """
        # 更新止损价格
        if self.stop_loss_price > 0:
            self.position_id.stop_loss_price = self.stop_loss_price

        # 更新止盈价格
        if self.stop_win_price > 0:
            self.position_id.stop_win_price = self.stop_win_price

        # 创建执行订单
        o = exchange.order(self.symbol_id.name)
        order_info = o.open_order(self.side, self.amount, self.execute_price, log=True)
        if not order_info:
            return
        self.order_uid = order_info['id']
        self.update_for_exchange(exchange)

    def update_for_exchange(self, exchange=None):
        """
        从交易所更新最新的order_info
        :return:
        """
        # 没有order_uid的时候不需要更新
        if not self.order_uid:
            return

        # 获取交易所对象
        if not exchange:
            exchange = self.trading_id.exchange_id.get_exchange()
        # 获取交易对对象
        symbol_name = self.symbol_id.name
        # 获取订单对象
        o = exchange.order(symbol_name)
        order_info = o.get_order_id_info(self.order_uid)
        if not order_info:
            self.state = 'canceled'
            logging.error("获取订单信息失败，订单号：{}".format(self.order_uid))
            return
            # raise exceptions.ValidationError("获取订单信息失败，订单号：{}".format(self.order_uid))

        if order_info['status'] == 'reduce_out':
            order_info['status'] = 'canceled'

        update_data = {
            "update_time": order_info['lastTradeTimestamp'],
            "state": order_info['status'],
            "price": order_info['price'],
            "amount": order_info['amount'],
            'execute_type': order_info['type'],
            'create_time': order_info["timestamp"]
        }
        # 更新订单信息
        self.update(update_data)
