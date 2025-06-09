import json

from odoo import api, fields, models, exceptions
from datetime import timedelta

import pandas as pd
import numpy as np
import ccxt
import time
from datetime import datetime
import logging
import math

# 设置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_now_datetime():
    """
    获取当前的时间
    """
    return datetime.now() + timedelta(hours=8)
    # return datetime.now()


class BollGridStrategy:
    def __init__(self, exchange, symbol, timeframe='1d', api_key=None, api_secret=None,
                 leverage=3, max_loss_per_grid=100, atr_multiplier=1.2):
        """
        初始化网格策略

        参数:
            exchange: 交易所名称('binance'/'bybit'等)
            symbol: 交易对 (如 'BTC/USDT')
            timeframe: K线周期
            api_key: API密钥
            api_secret: API秘钥
            leverage: 杠杆倍数
            max_loss_per_grid: 每个网格最大亏损额(美元)
            atr_multiplier: ATR倍数，用于确定网格数量
        """
        self.exchange = getattr(ccxt, exchange)({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        self.symbol = symbol
        self.timeframe = timeframe
        self.leverage = leverage
        self.max_loss_per_grid = max_loss_per_grid
        self.atr_multiplier = atr_multiplier

        # 策略状态
        self.is_running = False
        self.positions = []
        self.grid_prices = []
        self.upper_boundary = 0
        self.lower_boundary = 0
        self.mid_price = 0
        self.grid_count = 0
        self.current_price = 0

        logger.info(f"初始化策略: {symbol} 于 {exchange}, 杠杆: {leverage}x, 每格最大亏损: ${max_loss_per_grid}")

    def fetch_ohlcv(self, limit=30):
        """获取K线数据"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return None

    def calculate_bollinger_bands(self, df, window=20, num_std=2):
        """计算布林带"""
        df['sma'] = df['close'].rolling(window=window).mean()
        df['std'] = df['close'].rolling(window=window).std()
        df['upper'] = df['sma'] + (df['std'] * num_std)
        df['lower'] = df['sma'] - (df['std'] * num_std)
        df['mid'] = df['sma']
        return df

    def calculate_atr(self, df, window=14):
        """计算ATR"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr = true_range.rolling(window=window).mean()
        return atr

    def determine_grid_parameters(self):
        """确定网格参数"""
        df = self.fetch_ohlcv(limit=30)
        if df is None or len(df) < 20:
            logger.error("数据不足，无法确定网格参数")
            return False

        # 计算布林带
        df = self.calculate_bollinger_bands(df)

        # 计算ATR
        df['atr'] = self.calculate_atr(df)

        # 获取最新的布林带值和ATR
        latest = df.iloc[-2]  # 使用前一根K线的数据
        self.upper_boundary = latest['upper']
        self.lower_boundary = latest['lower']
        self.mid_price = latest['mid']
        self.current_price = df.iloc[-1]['close']

        # 确定网格数量基于ATR
        price_range = self.upper_boundary - self.lower_boundary
        atr = latest['atr']
        self.grid_count = max(5, min(50, int(price_range / (atr * self.atr_multiplier))))

        # 计算每个网格的间距
        grid_step = price_range / self.grid_count

        # 生成网格价格
        self.grid_prices = [self.lower_boundary + i * grid_step for i in range(self.grid_count + 1)]

        logger.info(f"网格参数: 上边界={self.upper_boundary}, 下边界={self.lower_boundary}, 中间价={self.mid_price}")
        logger.info(f"网格数量: {self.grid_count}, 网格间距: {grid_step:.2f}")
        logger.info(f"当前价格: {self.current_price}")

        return True

    def calculate_position_size(self, price, next_lower_price):
        """
        计算每个网格的仓位大小，确保最大亏损不超过设定值

        参数:
            price: 当前网格价格
            next_lower_price: 下一个网格价格(止损价)
        """
        price_diff_percent = abs(price - next_lower_price) / price
        # 最大亏损 = 仓位大小 * 价差百分比
        # 100 = 仓位大小 * 价差百分比
        position_size = self.max_loss_per_grid / price_diff_percent
        return position_size

    def setup_grid(self):
        """设置网格交易"""
        if not self.determine_grid_parameters():
            return False

        # 清空之前的仓位记录
        self.positions = []

        # 仅当价格低于中间价时开启网格策略
        if self.current_price > self.mid_price:
            logger.info("当前价格高于中间价，暂不开启网格")
            return False

        # 找到当前价格所在的网格区间
        current_grid_index = 0
        for i in range(len(self.grid_prices) - 1):
            if self.grid_prices[i] <= self.current_price < self.grid_prices[i + 1]:
                current_grid_index = i
                break

        # 计算每个网格的仓位
        total_investment = 0
        for i in range(current_grid_index, len(self.grid_prices) - 1):
            grid_price = self.grid_prices[i]
            next_price = self.grid_prices[i - 1] if i > 0 else self.lower_boundary

            # 计算该网格的仓位大小
            position_size = self.calculate_position_size(grid_price, next_price)

            # 记录需要下单的网格
            self.positions.append({
                'price': grid_price,
                'size': position_size,
                'filled': False,
                'order_id': None
            })

            total_investment += position_size

            logger.info(f"网格 #{i}: 价格={grid_price:.2f}, 仓位=${position_size:.2f}")

        logger.info(f"总投资: ${total_investment:.2f}")
        self.is_running = True
        return True

    def place_grid_orders(self):
        """下网格订单"""
        if not self.is_running:
            logger.info("网格策略未启动")
            return

        try:
            # 获取当前价格
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']

            for i, grid in enumerate(self.positions):
                if not grid['filled'] and current_price <= grid['price']:
                    # 下单
                    order = self.exchange.create_market_buy_order(
                        self.symbol,
                        grid['size'] / current_price * self.leverage
                    )

                    logger.info(f"触发网格 #{i}: 价格={grid['price']:.2f}, 执行买入, 订单ID={order['id']}")

                    # 更新订单状态
                    grid['filled'] = True
                    grid['order_id'] = order['id']

        except Exception as e:
            logger.error(f"下单失败: {e}")

    def check_boundary_conditions(self):
        """检查边界条件，超出边界则清仓停止"""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']

            # 检查是否超出网格边界
            if current_price > self.upper_boundary or current_price < self.lower_boundary:
                logger.warning(
                    f"价格 {current_price} 超出网格边界 [{self.lower_boundary:.2f}, {self.upper_boundary:.2f}]，准备清仓")
                self.close_all_positions()
                self.is_running = False
                return True
            return False

        except Exception as e:
            logger.error(f"检查边界条件失败: {e}")
            return False

    def close_all_positions(self):
        """清仓所有持仓"""
        try:
            # 获取当前持仓
            positions = self.exchange.fetch_positions(symbols=[self.symbol])

            for position in positions:
                if float(position['contracts']) > 0:
                    # 平仓
                    self.exchange.create_market_sell_order(
                        self.symbol,
                        position['contracts']
                    )
                    logger.info(f"清仓: {position['contracts']} 合约, 价值: ${float(position['notional']):.2f}")

            # 重置网格状态
            self.positions = []
            logger.info("已清仓所有持仓，网格策略停止")

        except Exception as e:
            logger.error(f"清仓失败: {e}")

    def run(self):
        """运行策略"""
        logger.info("开始运行网格策略")

        # 设置杠杆
        try:
            self.exchange.set_leverage(self.leverage, self.symbol)
            logger.info(f"设置杠杆为 {self.leverage}x")
        except Exception as e:
            logger.warning(f"设置杠杆失败: {e}")

        # 初始化网格
        if not self.setup_grid():
            logger.error("网格设置失败，策略未启动")
            return

        try:
            while True:
                # 检查是否需要清仓停止
                if self.check_boundary_conditions():
                    break

                # 执行网格交易
                self.place_grid_orders()

                # 每10秒检查一次
                time.sleep(10)

                # 每小时重新计算网格参数
                if datetime.now().minute == 0 and datetime.now().second < 10:
                    logger.info("重新计算网格参数")
                    self.close_all_positions()
                    if not self.setup_grid():
                        break

        except KeyboardInterrupt:
            logger.info("用户中断，清仓并退出")
            self.close_all_positions()
        except Exception as e:
            logger.error(f"策略执行错误: {e}")
            self.close_all_positions()


class GridTrading(models.Model):
    _name = 'fo.trading.grid.trading'
    _description = "智能网格策略"

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

    def _default_exchange(self):
        """
        获取默认交易所
        :return:
        """
        instance = self.env['fo.trading.exchange'].search([('is_default', '=', True)], limit=1)
        return instance.id

    @api.depends('exchange_id')
    def _compute_max_loss(self):
        """
        计算最大亏损
        :return:
        """
        for record in self:
            if not record.exchange_id:
                continue

            exchange = record.exchange_id.get_exchange()
            u = exchange.user("BTC/USDT:USDT")
            balance = u.get_balance()

            self.max_loss = balance * record.exchange_id.max_loss_rate_for_position / 100 * 2

    @api.onchange('a', 'b')
    def _onchange_a_b(self):
        """
        当a,b有变化的时候执行这段代码
        :return:
        """
        if not all([self.a, self.b]):
            return

        if self.a < self.b:
            raise exceptions.ValidationError("最大值a必须大于最小值b")

        # 计算出每个分段的值
        diff_value = (self.a - self.b) / 4

        # 计算出入场价格
        self.entry_a = self.a - diff_value
        self.entry_b = self.b + diff_value

        # 计算出止盈价格
        self.exit_a = self.entry_a + diff_value / 4
        self.exit_b = self.entry_b - diff_value / 4
        self.last_execute_time = fields.Datetime.now()
        self.next_execute_time = fields.Datetime.now()

    name = fields.Char("订单号", default=_default_name)

    create_year = fields.Integer('年', default=lambda x: get_now_datetime().year)
    create_month = fields.Integer('月', default=lambda x: get_now_datetime().month)
    create_day = fields.Integer('日', default=lambda x: get_now_datetime().day)

    state = fields.Selection([('1', '编辑中'), ('2', '运行中'), ('3', '已结束')], default='1', string="状态")

    timeframe = fields.Selection([('15m', '15分钟'), ('30m', '30分钟'), ('1h', '1小时'), ('4h', '4小时'),
                                  ('1d', '天线')], string='偏好周期', default='4h', required=True)
    symbol_id = fields.Many2one('fo.trading.symbol', string="交易对")
    exchange_id = fields.Many2one('fo.trading.exchange', string="交易所", default=_default_exchange)
    # 一些固定参数
    atr_rate = fields.Float("ATR系数", default=2.2, help="网格间距最大值为MA均线+ ATR系数 * ATR * 2")
    # grid_num = fields.Integer("网格数量", default=6, help="每个网格的收益其实就是atr_rate * 4 / grid_count")
    ema_len = fields.Integer("EMA均线长度", default=21, help="EMA均线长度")

    # max_loss = fields.Float("最大亏损", compute=_compute_max_loss, help="最大亏损金额", store=True)
    max_loss = fields.Float("最大亏损", required=True, default=10)
    max_profit = fields.Float("最大收益", default=0, help="记录在过程中最大的收益")
    long_profit = fields.Float("多头收益", default=0.0, help="多头收益")
    short_profit = fields.Float("空头收益", default=0.0, help="空头收益")
    last_execute_time = fields.Datetime("上次参数更新时间", default=fields.Datetime.now)
    next_execute_time = fields.Datetime("下次参数更新时间", default=fields.Datetime.now)

    # 依次从上往下，a,exit_a,entry_a, entry_b, exit_b, b, 网格参数变成固定参数
    a = fields.Float("最大值", default=0.0, help="网格区间的最大值，空头的止损价格")
    exit_a = fields.Float("多头止盈", default=0.0, help="多头的止盈价格")
    entry_a = fields.Float("空头入场价", default=0.0, help="空头入场价格")
    entry_b = fields.Float("多头入场价", default=0.0, help="多头入场价格")
    exit_b = fields.Float("空头止盈", default=0.0, help="空头的止盈价格")
    b = fields.Float("最小值", default=0.0, help="网格区间的最小值，多头的止损价格")

    # 动态参数
    now_grid_num = fields.Integer("网格数量", default=0, help="根据atr的变动来调整网格的数量")
    last_grid_index = fields.Integer("上次所在网格", default=0, help="上次所在网格位置")
    now_long_grid_positions = fields.Char("当前多头网格参数", help="当前多头网格参数json仓位列表")
    now_short_grid_positions = fields.Char("当前空头网格参数", help="当前空头网格参数json仓位列表")

    # now_atr_value = fields.Float("当前ATR值", default=0.0, help="m")
    # now_a = fields.Float("最大值", default=0.0, help="区间的最大值")
    # now_entry_a = fields.Float("当前A点入场价格", default=0.0)
    # now_b = fields.Float("最小值", default=0.0, help="区间的最小值")
    # now_entry_b = fields.Float("当前B点入场价格", default=0.0)
    # now_exit_a = fields.Float("当前A点出场价格", default=0.0, help="当前A点出场价格")
    # now_exit_b = fields.Float("当前B点出场价格", default=0.0, help="当前B点出场价格")
    # now_atr_value = fields.Float("当前ATR值", default=0.0, help="当前ATR值")
    # now_ema_value = fields.Float("当前EMA值", default=0.0, help="当前EMA值")
    # now_long_profit = fields.Float("当前多头收益", default=0.0, help="当前多头收益")
    # now_short_profit = fields.Float("当前空头收益", default=0.0, help="当前空头收益")
    # now_long_amount = fields.Float("当前多头仓位", default=0.0, help="当前多头仓位")
    # now_short_amount = fields.Float("当前空头仓位", default=0.0, help="当前空头仓位")
    # now_grid_index = fields.Integer("当前所在网格", default=0, help="当前所在网格位置")

    def _cron(self):
        """
        定时任务
        :return:
        """
        instances = self.search([('state', '=', '2')])

        for instance in instances:
            instance.run()
            # pass

    def auto_get_a_b(self):
        """
        自动获取a,b点位
        :return:
        """
        # 初始化交易所对象
        exchange = self.exchange_id.get_exchange()
        kd = exchange.kdata(self.symbol_id.name)

        # 开始更新数据
        kd.update_kdata(self.timeframe, 50)

        # 获取前一天ATR的值
        atr = kd.get_atr(self.timeframe, 14, ref=1)

        # 获取前一天的EMA的值
        ema = kd.get_ema(self.timeframe, self.ema_len, ref=1)

        # 计算atr_value的值
        atr_rate_value = atr * 2.1
        self.a = ema + atr_rate_value * 2
        self.b = ema - atr_rate_value * 2

    def init_args(self):
        """
        初始化数据
        1. 校验参数的正确性
        :return:
        """
        # self.now_a = 0.0
        # self.now_entry_a = 0.0
        # self.now_b = 0.0
        # self.now_entry_b = 0.0
        # self.now_atr_value = 0.0
        # self.now_ema_value = 0.0
        # self.now_long_profit = 0.0
        # self.now_short_profit = 0.0
        # self.now_long_amount = 0.0
        # self.now_short_amount = 0.0
        # # self.now_grid_positions = ''
        # self.now_long_grid_positions = ''
        # self.now_short_grid_positions = ''
        self.last_execute_time = fields.Datetime.now()
        self.next_execute_time = fields.Datetime.now()
        self.now_grid_num = 0
        self.last_grid_index = 0
        self.now_long_grid_positions = ''
        self.now_short_grid_positions = ''
        if not all([self.a, self.b]):
            # 如果没有设置a,b点位，则自动获取
            self.auto_get_a_b()
            self._onchange_a_b()

    def start(self):
        """
        开始监控
        :return:
        """
        self.state = '2'
        self.init_args()
        # 设置杠杆
        exchange = self.exchange_id.get_exchange()
        m = exchange.market(self.symbol_id.name)
        m.set_level(20)

    def stop(self):
        """
        结束运行
        :return:
        """
        self.state = '3'


class GridTradingStrategy(models.Model):
    _inherit = 'fo.trading.grid.trading'
    _description = "网格策略策略部分"

    def run(self):
        """
        核心运行部分
        多头核心运行
        空头核心运行
        :return:
        """
        exchange = self.exchange_id.get_exchange()
        # 初始化参数

        self.init_run(exchange)
        self.update_profit(exchange)

        # 进行止损的操作
        self._run(exchange, 'long')
        self._run(exchange, 'short')

    def _run(self, exchange, side):
        """
        封装运行
        :return:
        """
        # 进行止损判断
        self.stop_loss(exchange, side)

        # 数据校验
        # grid_positions = json.loads(self.now_grid_positions)
        long_grid_positions = json.loads(self.now_long_grid_positions)
        short_grid_positions = json.loads(self.now_short_grid_positions)
        grid_positions = long_grid_positions if side == 'long' else short_grid_positions
        if not grid_positions:
            logger.error("{} - 网格仓位数据为空".format(self.symbol_id.name))
            return False

        u = exchange.user(self.symbol_id.name)
        now_amount = u.get_position_amount(side)
        if now_amount:
            self.has_amount_run(exchange, side, now_amount)
        else:
            self.no_amount_run(exchange, side)

    def init_run(self, exchange):
        """
        初始化网格参数
        :return:
        """
        # 每过一个时间周期执行一次
        if fields.Datetime.now() < self.next_execute_time:
            return

        # 判断是否需要更新数据
        c = exchange.compute(self.symbol_id.name)
        o = exchange.order(self.symbol_id.name)
        kd = exchange.kdata(self.symbol_id.name)
        # 取消所以的挂单
        o.cancel_all_order()

        # 开始更新数据
        kd.update_kdata(self.timeframe, 100)

        # 获取前一天ATR的值， 用于计算每个网格的值
        atr = kd.get_atr(self.timeframe, 30, ref=1)

        grid_value = atr * 0.5
        # 计算网格 数量
        grid_num = int((self.exit_a - self.b) / grid_value)
        # 最小要5个网格
        self.now_grid_num = max(5, grid_num)
        # 计算多头和空头的数据参数
        long_grid_positions = c.compute_grid_positions(self.exit_a, self.b, self.now_grid_num, self.max_loss)
        short_grid_positions = c.compute_grid_positions(self.a, self.exit_b, self.now_grid_num, self.max_loss)
        if not all([long_grid_positions, short_grid_positions]):
            logger.error("{} - 网格仓位数据为空".format(self.symbol_id.name))
            return False
        # 格式化存储
        self.now_long_grid_positions = json.dumps(long_grid_positions)
        self.now_short_grid_positions = json.dumps(short_grid_positions)
        # 设置一下上次执行时间和下次执行时间
        next_time = c.get_next_run_time(fields.Datetime.now(), self.timeframe)
        self.next_execute_time = next_time
        self.last_execute_time = fields.Datetime.now()
        # 获取前一天的EMA的值
        # ema = kd.get_ema(self.timeframe, self.ema_len, ref=1)

        # 计算atr_value的值
        # atr_rate_value = atr * self.atr_rate
        # 计算entry_a, a的值
        # entry_a = ema + atr_rate_value
        # exit_a = entry_a + (atr_rate_value / 4)
        # a = entry_a + atr_rate_value
        # 计算entry_b, b的值
        # entry_b = ema - atr_rate_value
        # exit_b = entry_b - (atr_rate_value / 4)
        # b = entry_b - atr_rate_value

        # 计算网格数量， 15m一个ATR的值为一个网格
        # 先计算出grid_value的值
        # if self.timeframe == '15m':
        #     grid_value = atr
        # else:
        #     kd.update_kdata('15m', 100)
        #     grid_value = kd.get_atr('15m', 30, ref=1)
        # 0.8为系数
        # grid_value = grid_value * 1

        # 判断是否有所有的数据
        # if not all([a, b, entry_a, entry_b, atr, ema]):
        #     logger.error("{} - 网格策略参数不完整".format(self.symbol_id.name))
        #     logger.info(
        #         "当前的参数为：a={}, b={}, entry_a={}, entry_b={}, atr={}, ema={}".format(a, b, entry_a, entry_b, atr,
        #                                                                                  ema))
        #     return False

        # 进行赋值处理
        # self.now_a = a
        # self.now_exit_a = exit_a
        # self.now_entry_a = entry_a
        # self.now_b = b
        # self.now_entry_b = entry_b
        # self.now_exit_b = exit_b
        # self.now_atr_value = atr
        # self.now_ema_value = ema
        # 获取grid_positions的值
        # grid_positions = c.compute_grid_positions(a, b, self.grid_num, self.max_loss)

        # self.now_grid_positions = json.dumps(grid_positions)

    def has_amount_run(self, exchange, side, now_amount):
        """
        有仓位的运行, 直接进行网格的挂单和卖单操作
        :param exchange:
        :param side:
        :param now_amount:
        :return:
        """
        # 初始化参数
        m = exchange.market(self.symbol_id.name)
        c = exchange.compute(self.symbol_id.name)
        o = exchange.order(self.symbol_id.name)
        # grid_positions = json.loads(self.now_grid_positions)
        long_grid_positions = json.loads(self.now_long_grid_positions)
        short_grid_positions = json.loads(self.now_short_grid_positions)
        grid_positions = long_grid_positions if side == 'long' else short_grid_positions

        # 计算出当前价格和当前所属的网格位置
        now_price = m.get_now_price()
        now_grid_index = c.get_now_grid_index(grid_positions, now_price)
        if not now_grid_index:
            return

        # if now_amount != getattr(self, 'now_{}_amount'.format(side)):
        #     # 如果当前仓位和记录的仓位不一致，则更新当前仓位
        #     setattr(self, 'now_{}_amount'.format(side), now_amount)
        #     # 取消所有挂单重新进行挂单
        #     o.cancel_close_order(side)
        #     o.cancel_open_order(side)

        if now_grid_index != self.last_grid_index:
            self.last_grid_index = now_grid_index
            o.cancel_close_order(side)
            o.cancel_open_order(side)
        # 如果网格变动大于1则全部取消
        # if abs(now_grid_index - self.now_grid_index) > 1:
        # else:
        #     # 只跳动一个网格
        #     if now_grid_index < self.now_grid_index:

        min_amount = m.get_min_amount()

        # 进行买入的操作
        buy_position_amount, price = c.get_index_grid_need_buy(side, grid_positions, now_grid_index)
        need_buy_amount = buy_position_amount - now_amount
        need_buy_amount -= o.get_open_order_amount(side, price)
        if need_buy_amount > min_amount:
            # 进行挂单
            o.open_order(side, need_buy_amount, price, log=True)

        # 进行卖出的操作
        sell_position_amount, price = c.get_index_grid_need_sell(side, grid_positions, now_grid_index)
        need_sell_amount = now_amount - sell_position_amount
        need_sell_amount -= o.get_close_order_amount(side, price)
        if need_sell_amount > min_amount:
            # 进行卖出挂单
            o.close_order(side, need_sell_amount, price, log=True)

    def no_amount_run(self, exchange, side):
        """
        没有仓位的运行
        需要等待价格满足才能进行买入，需要已市价买入基础仓位，开启网格
        :param exchange:
        :param side:
        :return:
        """
        # 初始化参数
        m = exchange.market(self.symbol_id.name)
        now_price = m.get_now_price()
        min_amount = m.get_min_amount()

        # 如果是多头，价格未在entry_b价格之下就不买入
        if side == 'long' and 0 < self.entry_b < now_price:
            return

        # 如果是空头，价格未在entry_a价格之上就不买入
        if side == 'short' and self.entry_a > 0 and now_price < self.entry_a:
            return

        # 进一步加载参数
        c = exchange.compute(self.symbol_id.name)
        o = exchange.order(self.symbol_id.name)
        # grid_positions = json.loads(self.now_grid_positions)
        long_grid_positions = json.loads(self.now_long_grid_positions)
        short_grid_positions = json.loads(self.now_short_grid_positions)
        grid_positions = long_grid_positions if side == 'long' else short_grid_positions

        now_grid_index = c.get_now_grid_index(grid_positions, now_price)
        if not now_grid_index:
            return

        # 进行买入
        buy_position_amount, price = c.get_index_grid_need_buy(side, grid_positions, now_grid_index)
        need_buy_amount = buy_position_amount - o.get_open_order_amount(side, price)
        if need_buy_amount > min_amount:
            # 市价买入
            o.open_order(side, need_buy_amount, log=True)

    def update_profit(self, exchange):
        """
        更新当前收益
        :return:
        """
        try:
            position_dict = exchange.exchange.fetch_position(self.symbol_id.name)
            position_info_list = position_dict['info']
        except Exception as e:
            return False

        for position in position_info_list:
            side = position['mode']
            profit = float(position['pnl_pnl']) + float(position['unrealised_pnl'])

            if side == 'dual_long':
                self.long_profit = profit
            else:
                self.short_profit = profit

            all_profit = self.long_profit + self.short_profit
            if all_profit > self.max_profit:
                self.max_profit = all_profit

    def stop_loss(self, exchange, side):
        """
        停止运行
        :return:
        """
        # 没有数据不止损
        if not all([self.a, self.b]):
            return

            # 没有收益说明没有仓位，不止损
        if self.short_profit == 0 and self.long_profit == 0:
            return

        m = exchange.market(self.symbol_id.name)
        now_price = m.get_now_price()

        need_stop = False
        # 如果超出范围进行止损
        if side == 'long' and now_price < self.b:
            need_stop = True
        elif side == 'short' and now_price > self.a:
            need_stop = True

        # 如果已经超出最大亏损进行止损
        all_profit = self.long_profit + self.short_profit
        if all_profit < -self.max_loss:
            need_stop = True

        if not need_stop:
            return

        # 进行止损
        o = exchange.order(self.symbol_id.name)
        u = exchange.user(self.symbol_id.name)
        self.state = '3'
        long_amount = u.get_position_amount('long')
        short_amount = u.get_position_amount('short')
        if long_amount:
            o.close_order('long', long_amount, log=True)
        if short_amount:
            o.close_order('short', short_amount, log=True)
        o.cancel_all_order()


if __name__ == "__main__":
    # 策略参数
    exchange_id = "binance"  # 交易所
    symbol = "BTC/USDT"  # 交易对
    timeframe = "1d"  # K线周期
    leverage = 3  # 杠杆倍数
    max_loss = 100  # 每网格最大亏损(美元)
    atr_multiplier = 1.2  # ATR倍数，用于网格数量计算

    # API密钥(请替换为您自己的密钥)
    api_key = "YOUR_API_KEY"
    api_secret = "YOUR_API_SECRET"

    # 初始化并运行策略
    strategy = BollGridStrategy(
        exchange=exchange_id,
        symbol=symbol,
        timeframe=timeframe,
        api_key=api_key,
        api_secret=api_secret,
        leverage=leverage,
        max_loss_per_grid=max_loss,
        atr_multiplier=atr_multiplier
    )

    strategy.run()
