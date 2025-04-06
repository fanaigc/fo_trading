import logging

from odoo import api, fields, models, exceptions
import ccxt
from ..apis import CcxtApis
from datetime import datetime, timedelta


def get_now_datetime():
    """
    获取当前的时间
    """
    return datetime.now() + timedelta(hours=8)
    # return datetime.now()


class TradingSub(models.Model):
    _name = 'fo.trading.trading.sub'
    _description = "加仓订单"

    state = fields.Selection([('1', '监控中'), ('2', '已完成'), ('-1', "无法交易")], default='1', string="状态")
    entry_price = fields.Float("入场价格", digits=(16, 9), default=0, help="入场价格，0为市价买入")
    stop_loss_price = fields.Float("止损价格", digits=(16, 9), help="止损价格，如果不输入默认为20根K线最小值")
    buy_price = fields.Float("实际买入价格", digits=(16, 9), default=0)
    max_loss = fields.Float("最大亏损")
    need_buy_amount = fields.Float("需要买入amount数量")
    before_amount = fields.Float("加仓前的amount")
    exchange_order_id = fields.Char("交易ID")

    trading_id = fields.Many2one("fo.trading.trading", "父单", required=True)
    error_msg = fields.Char("错误说明")
    add_remark = fields.Html("加仓说明")

    @api.model_create_multi
    def create(self, vals_list):
        instances = super().create(vals_list)
        for instance in instances:
            instance.stop_loss_price = instance.trading_id.stop_loss_price
            instance.before_amount = instances.trading_id.now_amount
            instance.add_corn()
        return instances

    @api.model
    def unlink(self):
        for record in self:
            if record.state != '1':
                raise exceptions.UserError("只有在监控中的加仓记录才能删除！")
        return super().unlink()

    def add_corn(self):
        """
        加仓的核心方法
        1. 计算加仓最大亏损金额，并写入参数
        2. 计算需要加仓数量
        3. 实行加仓操作
        """
        # 只有状态为监控中才可以交易
        if self.state != '1':
            return

        # 1. 计算最大加仓亏损金额
        trading_instance = self.trading_id
        symbol_name = trading_instance.symbol_id.name
        exchange = trading_instance.exchange_id.get_exchange()
        c = exchange.compute(symbol_name)
        m = exchange.market(symbol_name)
        u = exchange.user(symbol_name)
        o = exchange.order(symbol_name)
        side = trading_instance.side
        if not self.max_loss:
            # 1.1 获取当前在监控中的所有最大亏损的和
            all_max_loss_money = 0
            for instance in self.env['fo.trading.trading'].search([('state', '=', '1')]):
                all_max_loss_money += instance.max_loss
            # 1.2 获取所有balance
            max_balance = u.get_balance() - all_max_loss_money
            # 1.3 计算出max_loss
            self.max_loss = max_balance * trading_instance.exchange_id.add_max_loss_rate / 100

            # 先计算出当前父类的最大亏损金额
            if trading_instance.is_has_position:
                max_loss = u.get_appoint_stop_loss_max_loss(trading_instance.side, self.stop_loss_price)
            else:
                max_loss = trading_instance.max_loss
            # 计算出当前max_loss
            now_max_loss = max_loss + self.max_loss
            # 取当前计算出来的最大亏损和父类已经存在的最大亏损取最大值为实际的最大亏损
            trading_instance.max_loss = max(now_max_loss, trading_instance.max_loss)

        # 2. 计算需要加仓数量
        if not self.need_buy_amount:
            entry_price = self.entry_price
            if not self.entry_price:
                entry_price = m.get_now_price()
            self.need_buy_amount = c.get_buy_amount_for_stop_price(trading_instance.side,
                                                                   self.stop_loss_price,
                                                                   self.max_loss,
                                                                   entry_price)
        # 2.1 如果还是没有需要购买的amount，则退出交易
        if not self.need_buy_amount:
            self.state = '-1'
            self.error_msg = '无法计算出买入仓位！'
            return

        # 3. 实行加仓操作
        need_buy_amount = self.need_buy_amount
        # 3.1 市价买入的操作
        if self.entry_price == 0:
            logging.info("{} - 准备市价买入：{}".format(symbol_name, need_buy_amount))
            try:
                order_info = o.open_order(side, need_buy_amount, log=True)
                self.exchange_order_id = order_info['id']

            except Exception as e:
                self.state = '-1'
                self.error_msg = '市价买入失败！异常值：{}'.format(e)
                logging.error(self.error_msg)

            buy_price = u.get_position_avg_buy_price(side)
            if not buy_price:
                self.state = '-1'
                self.error_msg = '市价买入后，还是没有仓位'
                logging.error(self.error_msg)

            self.state = '2'
            self.buy_price = buy_price
            return
        # 3.2 限价买入的操作
        # 3.2.1 有订单，则判断订单是否成交
        if self.exchange_order_id:
            # 判断交易订单是否已经结束
            if not o.order_is_closed(self.exchange_order_id):
                return
            # 交易完成后计算最大亏损额度
            max_loss = c.get_max_loss(side, self.stop_loss_price)
            if max_loss > trading_instance.max_loss:
                trading_instance.max_loss = max_loss

            # 交易结束后进行赋值
            self.buy_price = self.entry_price
            self.state = '2'
            return

        # 3.2.2 没有订单，则进行挂单
        logging.info("{} - 准备限价：{}, 买入：{}".format(symbol_name, self.entry_price, need_buy_amount))

        try:
            order_info = o.open_order(side, need_buy_amount, self.entry_price, log=True)
            self.exchange_order_id = o.get_order_id(order_info)
        except Exception as e:
            self.state = '2'
            self.error_msg = '限价单买入失败！异常值：{}'.format(e)
            logging.error(self.error_msg)


class Trading(models.Model):
    _name = 'fo.trading.trading'
    _description = "手动交易"
    _inherit = ['mail.thread', 'mail.activity.mixin']

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

    name = fields.Char("交易编号", default=_default_name)
    state = fields.Selection([('-1', '编辑中'), ("0", "已过检"), ('1', '监控中'), ('2', '已结束')], default='-1',
                             string="状态",
                             tracking=True)
    entry_price = fields.Float("入场价格", digits=(16, 9), default=0, help="入场价格，0为市价买入", required=True,
                               tracking=True)
    buy_price = fields.Float("实际买入价格", digits=(16, 9), default=0,
                             tracking=True)
    stop_loss_price = fields.Float("止损价格", digits=(16, 9), required=True,
                                   help="止损价格，如果不输入默认为20根K线最小值", tracking=True)
    stop_win_price = fields.Float("止盈价格", digits=(16, 9), help="如果没有止盈价格，则动态止盈", tracking=True)
    side = fields.Selection([('long', "做多"), ('short', "做空")], string="方向", required=True)
    now_amount = fields.Float("当前的amount")
    max_loss = fields.Float("最大亏损", tracking=True)
    timeframe = fields.Selection([
        ('1m', '1分钟'), ('5m', '5分钟'), ('15m', '15分钟'),
        ('30m', '30分钟'), ('1h', '1小时'), ('4h', '4小时'),
        ('1d', '天线'), ('1w', '周线')], string='参考周期')

    open_remark = fields.Html("开仓说明")
    close_remark = fields.Html("平仓总结")
    pnl = fields.Float("收益额", digits=(16, 3))
    pnl_fee = fields.Float("手续费", digits=(16, 3))
    is_has_position = fields.Boolean("是否拥有过仓位", default=False)
    exchange_order_id = fields.Char("交易所订单ID")
    error_msg = fields.Char("错误信息")
    open_time = fields.Char("开仓时间", help='开仓时间可以帮助进行获取收益率')

    @api.depends("pnl", "max_loss")
    def _compute_pnl_rate(self):
        """
        自动计算收益率
        """
        for record in self:
            if record.max_loss == 0:
                record.pnl_rate = 0
            else:
                record.pnl_rate = record.pnl / record.max_loss

    pnl_rate = fields.Float("盈亏比", store=True, digits=(16, 3), help="针对最大亏损计算比例",
                            compute=_compute_pnl_rate)

    create_year = fields.Integer('年', default=lambda x: get_now_datetime().year)
    create_month = fields.Integer('月', default=lambda x: get_now_datetime().month)
    create_day = fields.Integer('日', default=lambda x: get_now_datetime().day)

    # 外键字段
    symbol_id = fields.Many2one("fo.trading.symbol", string="币种", required=True)
    exchange_id = fields.Many2one("fo.trading.exchange", string="交易所")
    trading_sub_ids = fields.One2many('fo.trading.trading.sub', 'trading_id', string="加仓订单")

    # exchange_type = fields.Selection([('binance', 'binance'), ('gate', 'gate')],
    #                                  default='binance', string="交易所类型")
    #
    # api_key = fields.Char("API Key")
    # api_secret = fields.Char("API Secret")


class TradingButton(models.Model):
    _inherit = 'fo.trading.trading'

    def _cron(self):
        """
        定时任务
        """
        # 查询所有正在运行中的订单
        instance = self.search([('state', '=', '1')], limit=1)
        if instance:
            # 按顺序执行核心
            instance.core()

            # 核心执行完毕后，执行加仓操作
            for sub_instance in instance.trading_sub_ids:
                sub_instance.add_corn()

    def set_default_exchange(self):
        """
        设置默认交易所
        """
        instance = self.exchange_id.search([('is_default', '=', True)], limit=1)
        if not instance:
            raise exceptions.ValidationError("请先设置默认交易所在进行交易！！")
        self.exchange_id = instance.id

    def set_max_loss(self, exchange):
        """
        设置最大亏损金额
        1. 获取当前所有余额
        2. 计算1%来作为最大亏损金额进行赋值
        """
        # 1.1 获取当前在监控中的所有最大亏损的和
        all_max_loss_money = 0
        for instance in self.env['fo.trading.trading'].search([('state', '=', '1')]):
            all_max_loss_money += instance.max_loss

        # 1.2 获取所有balance
        u = exchange.user(self.symbol_id.name)
        max_balance = u.get_balance() - all_max_loss_money

        # 2. 获取配置的最大亏损百分比
        self.max_loss = max_balance * self.exchange_id.open_max_loss_rate / 100

    def check_args(self):
        """
        校验参数
        1. 检查是否存在可以交易的仓位
        2. 查看盈亏比是否有1：1，否则不可以进行交易
        """
        # 判断一下是否已经存在当前币种正在交易的订单，存在则不允许校验通过
        instance = self.search([('state', '=', '1'), ('symbol_id', '=', self.symbol_id.id)], limit=1)
        if instance:
            raise exceptions.ValidationError(
                "当前币种：{}，已经存在正在交易的订单，不允许重复创建！".format(self.symbol_id.name))
        self.set_default_exchange()
        exchange = self.exchange_id.get_exchange()
        self.set_max_loss(exchange)
        symbol_name = self.symbol_id.name
        c = exchange.compute(symbol_name)
        m = exchange.market(symbol_name)
        # u = exchange.user(symbol_name)

        now_price = m.get_now_price()
        entry_price = self.entry_price
        if not self.entry_price:
            entry_price = now_price

        # 1. 检查是否存在可以交易的仓位
        need_buy_amount = c.get_buy_amount_for_stop_price(self.side,
                                                          self.stop_loss_price,
                                                          self.max_loss,
                                                          entry_price)
        if not need_buy_amount:
            raise exceptions.ValidationError("当前止损价格和入场价格无法计算出最小仓位！")
        # 2. 查看盈亏比是否有1：1，否则不可以进行交易
        ykb = 0
        syl = 0
        if self.stop_win_price:
            if self.side == 'long':
                ykb = (self.stop_win_price - entry_price) / (entry_price - self.stop_loss_price)
                syl = (self.stop_win_price - entry_price) / entry_price
            elif self.side == 'short':
                ykb = (entry_price - self.stop_win_price) / (self.stop_loss_price - entry_price)
                syl = (entry_price - self.stop_win_price) / entry_price

            # 盈亏比小于1不交易
            if ykb < 1:
                raise exceptions.ValidationError("盈亏比小于1不适合交易！")

            if syl < 0.005:
                raise exceptions.ValidationError("收益率0.5%都没有就别做交易了!!")
        level = min(c.get_max_lever(entry_price, self.stop_loss_price), m.max_level)
        m.set_level(level)
        self.state = '0'

    def back_check(self):
        """
        回退状态
        """
        self.state = '-1'
        self.name = self._default_name()
        # 删除所有的加仓记录
        for instance in self.trading_sub_ids:
            instance.unlink()

    def start(self):
        """
        程序启动
        """
        self.state = '1'
        self.core()

    def add(self):
        """
        执行加仓操作
        1. 判断当前是否可以进行加仓
        2. 弹出加仓form图表
        """
        # 1. 判断当前是否可以进行加仓
        instances = self.trading_sub_ids
        can_add = True
        for instance in instances:
            if instance.state == '1':
                can_add = False
                break
        if not can_add:
            raise exceptions.ValidationError("当前还有为加仓成功的订单，不可以进行加仓！")

        # 2. 弹出form图表
        return {
            'name': "加仓",
            'type': "ir.actions.act_window",
            'res_model': 'fo.trading.trading.sub',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_trading_id': self.id
            }
        }

    def stop(self):
        """
        程序停止
        """
        exchange = self.exchange_id.get_exchange()
        o = exchange.order(self.symbol_id.name)
        u = exchange.user(self.symbol_id.name)
        # 先清仓00
        now_amount = u.get_position_amount(self.side)
        if now_amount:
            # 先执行一个平仓
            o.close_order(self.side, now_amount)
            # 在计算一下这一单的收益情况
            self.core_has_position(exchange)

        # 取消所有挂单
        o.cancel_all_order()

        self.state = '2'

    def core(self):
        """
        量化核心代码，需要先初始化交易所对象
        1. 检查是否拥有过仓位
        2. 没有仓位 - 监控买入
        3. 有仓位 - 监控是否平仓
        """
        exchange = self.exchange_id.get_exchange()

        if self.is_has_position:
            self.core_has_position(exchange)
        else:
            self.core_not_position(exchange)

    def core_not_position(self, exchange):
        """
        监控买入逻辑
        1. 判断是否有仓位
        2. 无仓位 进行挂单
            1. 计算需要买入的仓位价值
            2. 入场价格为0，直接买入
            3. 有入场价格，判断是否挂单
            4. 进行挂单操作
        3. 有仓位 修改仓位状态
        """
        symbol_name = self.symbol_id.name
        m = exchange.market(symbol_name)
        u = exchange.user(symbol_name)
        o = exchange.order(symbol_name)
        kd = exchange.kdata(symbol_name)
        c = exchange.compute(symbol_name)

        now_value = u.get_position_value(side=self.side)
        # 有仓位 修改仓位状态
        if now_value:
            self.is_has_position = True
            self.open_time = u.get_open_time(self.side)
            return

        # 无仓位 进行挂单
        # 1. 计算需要买入的仓位价值
        need_buy_amount = c.get_buy_amount_for_stop_price(self.side,
                                                          self.stop_loss_price,
                                                          self.max_loss,
                                                          self.entry_price)
        if not need_buy_amount:
            self.state = '2'
            logging.error("未计算出可以购买的仓位，不进行购买！")
            return

        # 2. 判断一下entry_price是否为0，是否选择市价直接买进
        if self.entry_price == 0:
            logging.info("{} - 准备市价买入：{}".format(symbol_name, need_buy_amount))
            try:
                order_info = o.open_order(self.side, need_buy_amount, log=True)
                self.exchange_order_id = order_info['id']

            except Exception as e:
                self.state = '2'
                self.error_msg = '市价买入失败！异常值：{}'.format(e)
                logging.error(self.error_msg)

            buy_price = u.get_position_avg_buy_price(self.side)
            if not buy_price:
                self.state = '2'
                self.error_msg = '市价买入后，还是没有仓位'
                logging.error(self.error_msg)

            self.is_has_position = True
            self.buy_price = buy_price
            return

        # 3. 限价进行买入
        # 先检查一下订单号是否已经成交
        # if self.exchange_order_id:
        #     state = o.get_order_info_status(self.exchange_order_id)
        #     # 判断状态是否已经成交
        #     if state == 1:
        #         # 已经成功买入
        #         self.is_has_position = True
        #         self.buy_price = self.entry_price
        #         return

        # 3.1 先查看entry_price已经挂单的amount
        amount = o.get_open_order_amount(self.side, self.entry_price)
        need_buy_amount = need_buy_amount - amount
        if need_buy_amount > 0:
            logging.info("{} - 准备限价：{}, 买入：{}".format(symbol_name, self.entry_price, need_buy_amount))

            try:
                order_info = o.open_order(self.side, need_buy_amount, self.entry_price, log=True)
                self.exchange_order_id = o.get_order_id(order_info)
            except Exception as e:
                self.state = '2'
                self.error_msg = '限价单买入失败！异常值：{}'.format(e)
                logging.error(self.error_msg)

    def core_has_position(self, exchange):
        """
        监控平仓逻辑
        1. 查看当前仓位是否存在
        2. 不存在则更新订单状态
        3. 存在则进行挂止损和止盈单
        """
        symbol_name = self.symbol_id.name
        m = exchange.market(symbol_name)
        u = exchange.user(symbol_name)
        o = exchange.order(symbol_name)
        kd = exchange.kdata(symbol_name)
        c = exchange.compute(symbol_name)
        now_amount = u.get_position_amount(self.side)
        self.now_amount = now_amount

        # 不存在则更新订单状态， 结束所有程序运行
        if not now_amount:
            self.error_msg = '已经没有仓位了'
            self.state = '2'
            # 计算收益
            info = u.get_open_time_pnl_info(self.side, self.open_time)
            # info = o.get_last_close_order_info()
            self.pnl = info['pnl']
            self.pnl_fee = info['pnl_fee']
            return

        # 更新止损
        o.stop_order_for_price(self.side, self.stop_loss_price)

        # 更新止盈
        if not self.stop_win_price:
            return
        now_close_amount = o.get_close_order_amount(self.side, self.stop_win_price)
        # 如果在对应价位没有挂单止盈，说明止盈价格已经改动，取消所有挂单重新进行挂单
        if not now_close_amount:
            o.cancel_close_order(self.side, log=True)
        need_close_amount = now_amount - now_close_amount
        if need_close_amount:
            o.close_order(self.side, need_close_amount, self.stop_win_price, log=True)
