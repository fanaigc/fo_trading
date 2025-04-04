from odoo import api, fields, models, exceptions
from datetime import datetime, timedelta


def get_now_datetime():
    """
    获取当前的时间
    """
    return datetime.now() + timedelta(hours=8)
    # return datetime.now()


class StrategyTrading(models.Model):
    _name = "fo.trading.strategy.trading"
    _description = "策略交易"

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
    create_year = fields.Integer('年', default=lambda x: get_now_datetime().year)
    create_month = fields.Integer('月', default=lambda x: get_now_datetime().month)
    create_day = fields.Integer('日', default=lambda x: get_now_datetime().day)
    strategy_type = fields.Selection([("double_ema", "双均线策略")], default='double_ema', string="策略")
    # 公用参数
    state = fields.Selection([('-1', '编辑中'), ('1', '监控中'), ('2', '已结束')], default='-1')
    side = fields.Selection([("long", "做多"), ("short", "做空")], required=True, string="方向")
    timeframe = fields.Selection([
        ('1m', '1分钟'), ('5m', '5分钟'), ('15m', '15分钟'),
        ('30m', '30分钟'), ('1h', '1小时'), ('4h', '4小时'),
        ('1d', '天线'), ('1w', '周线')], string='时间周期', default='15m', required=True)
    max_loss = fields.Float("最大亏损金额", default=10, required=True)
    last_c = fields.Float("上次收盘价")
    last_o = fields.Float("上次开盘价")
    last_h = fields.Float("上次最高价")
    last_l = fields.Float("上次最低价")

    # 外键字段
    symbol_id = fields.Many2one('fo.trading.symbol', "交易对", required=True)
    exchange_id = fields.Many2one("fo.trading.exchange", "交易所", required=True)
    trading_ids = fields.One2many("fo.trading.strategy.trading.sub",
                                  "trading_id", string="订单列表")

    def _cron_run(self):
        """
        自动运行任务
        :return:
        """
        instances = self.search([('state', '=', '1')])
        for instance in instances:
            instance._run()

    def _run(self):
        """
        开始策略检测
        """
        if self.strategy_type == 'double_ema':
            self.double_ema_start()
        # exchange = self.exchange_id.get_exchange()
        # exchange.side = self.side
        # exchange.timeframe = self.timeframe
        # exchange.max_stop_loss = self.max_stop_loss
        #
        # if self.strategy_type == 'double_ema':
        #     if not all([self.double_ema_fast_num, self.double_ema_slow_num, self.double_stop_loss_max_k_num]):
        #         raise exceptions.ValidationError("缺少参数，无法正常运行策略！")
        #     exchange.double_ema_fast_num = self.double_ema_fast_num
        #     exchange.double_ema_slow_num = self.double_ema_slow_num
        #     exchange.double_ema_stop_loss_max_k_num = self.double_ema_stop_loss_max_k_num
        #     instance = double_ema.Strategy(exchange)
        #     instance.start()

    def start(self):
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

        exchange = self.exchange_id.get_exchange()
        m = exchange.market(self.symbol_id.name)
        m.set_max_level()
        self.state = '1'

    def stop(self):
        """
        停止交易
        :return:
        """
        self.state = '2'


class StrategyTradingSub(models.Model):
    _name = "fo.trading.strategy.trading.sub"
    _description = "策略子订单"

    name = fields.Char("交易编号")
    is_now_trading = fields.Boolean("是否是当前订单")
    side = fields.Selection([("long", "做多"), ("short", "做空")], required=True, string="方向")
    entry_price = fields.Float("进场价格")
    exit_price = fields.Float("退出价格")
    exit_time = fields.Datetime("退出时间")
    max_loss = fields.Float("最大亏损金额")
    pnl = fields.Float("收益额", digits=(16, 3))
    pnl_fee = fields.Float("手续费", digits=(16, 3))
    exchange_order_id = fields.Char("记录订单ID")
    error_msg = fields.Char("错误信息")

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

    # 外键字段
    trading_id = fields.Many2one("fo.trading.strategy.trading", "父订单")
