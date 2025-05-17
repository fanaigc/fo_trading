from odoo import api, fields, models, exceptions

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


class GridTrading(models.Model):
    _name = 'fo.trading.grid.trading'
    _description = "网格交易"

    name = fields.Char("网格名称")
    exchange_id = fields.Many2one('fo.trading.exchange', string="交易所")
    symbol = fields.Char("交易对")
    grid_count = fields.Integer("网格数量", default=10)
    grid_size = fields.Float("网格间距", default=0.01)
    grid_price = fields.Float("网格价格", default=0.0)
    grid_amount = fields.Float("网格数量", default=0.01)
    grid_type = fields.Selection([('buy', '买入'), ('sell', '卖出')], string="网格类型", default='buy')


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
