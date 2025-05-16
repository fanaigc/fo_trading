from odoo import exceptions
from .base import BaseFunc
from .market import Market
from .user import User
from datetime import datetime, timedelta


class Compute(BaseFunc):
    def __init__(self, symbol, exchange, *args, **kwargs):
        super(Compute, self).__init__(symbol, exchange, *args, **kwargs)
        # 初始化一些交易参数
        self.m = Market(symbol=symbol, exchange=self.exchange, *args, **kwargs)
        self.u = User(symbol=symbol, exchange=self.exchange, *args, **kwargs)

    def get_buy_amount_for_stop_price(self, side, stop_loss_price, max_loss_money, now_price=0):
        """
        根据止损几个和最大亏损价格计算投资的amount
        这个amount应该忽略所有的交易所特性，只获得对应价格的amount，比如比特币50000元，amount-0.1就是购买5000元
        :param side:
        :param now_price: 购买价格
        :param stop_loss_price:
        :param max_loss_money:
        :return:
        """
        commission = 0.05 / 100  # 手续费 0.05%
        slip_point = 0.01 / 100  # 滑点 0.01%
        if not now_price:
            now_price = self.m.get_now_price()

        if side == 'long' and now_price > stop_loss_price:
            # 多头止损
            now_price = now_price * (1 + slip_point)
            stop_loss_price = stop_loss_price * (1 - slip_point)
            amount = max_loss_money / (now_price - stop_loss_price +
                                       now_price * commission + stop_loss_price * commission)
        elif side == 'short' and now_price < stop_loss_price:
            # 空头止损
            now_price = now_price * (1 - slip_point)
            stop_loss_price = stop_loss_price * (1 + slip_point)
            amount = max_loss_money / (stop_loss_price - now_price +
                                       now_price * commission + stop_loss_price * commission)
        else:
            return 0

        # amount = amount / self.m.amount_size
        # amount = self.exchange.amount_to_precision(self.symbol, amount)
        min_amount = self.m.get_min_amount()

        if float(amount) >= min_amount:
            # return amount
            # if self.exchange.name == 'Gate.io':
            #     return self.m.get_can_order_amount(amount)
            return self.m.get_can_order_amount(amount)
        return 0

    def get_max_loss(self, side, stop_loss_price):
        """
        获取最大亏损金额
        正数是亏损，负数是赚取
        :param side:
        :param stop_loss_price:
        :return:
        """
        buy_price = self.u.get_position_avg_buy_price(side)
        now_amount = self.u.get_position_amount(side)

        commission = 0.05 / 100  # 手续费 0.05%
        buy_commission = buy_price * commission * now_amount
        stop_loss_commission = stop_loss_price * commission * now_amount
        all_commission = buy_commission + stop_loss_commission
        max_loss = 0
        if side == 'long':
            max_loss = (buy_price - stop_loss_price) * now_amount
        elif side == 'short':
            max_loss = (stop_loss_price - buy_price) * now_amount
        return max_loss + all_commission

    @staticmethod
    def get_max_lever(entry_price, exit_price):
        """
        获取最大杠杆等级
        # 1. 计算入场和退出亏损的百分比
        # 2. 计算杠杆 100 / 最大亏损百分比
        # 3. 优化杠杆 int后 - 1 最小是1
        :param entry_price: 入场价格
        :param exit_price:  退出价格
        :return:
        """
        loss_rate = abs(entry_price - exit_price) / entry_price * 100
        max_lever = 100 / loss_rate
        if max_lever < 1:
            raise ValueError("最大杠杆小于1，不可以进行交易！！")

        return max(int(max_lever) - 1, 1)

    from datetime import datetime, timedelta

    @staticmethod
    def get_next_run_time(now: datetime, timeframe: str) -> datetime:
        """
        根据当前时间和时间框架，返回下次运行策略的时间点
        :param now: 当前时间（datetime 对象）
        :param timeframe: 时间周期字符串，支持 '5m', '15m', '30m', '1h', '4h', '1d', '1w'
        :return: datetime 对象，表示下一次运行时间
        """

        # 定义各周期对应的分钟数
        timeframe_minutes = {
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240,
        }

        if timeframe in timeframe_minutes:
            minutes = timeframe_minutes[timeframe]
            # 当前已经过的分钟数
            total_minutes = now.hour * 60 + now.minute
            # 找到下一个倍数点
            next_minutes = ((total_minutes // minutes) + 1) * minutes
            # 计算目标时间的小时和分钟
            next_hour = next_minutes // 60
            next_minute = next_minutes % 60
            # 构造新的 datetime 对象
            next_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=next_hour,
                                                                                           minutes=next_minute)
            if next_time <= now:
                next_time += timedelta(minutes=minutes)
            return next_time

        elif timeframe == '1d':
            # 每天的00:00
            next_day = now.date() + timedelta(days=1)
            return datetime.combine(next_day, datetime.min.time())

        elif timeframe == '1w':
            # 每周一的00:00
            days_ahead = 7 - now.weekday()  # 如果今天是周一，则 +7
            if days_ahead == 0:
                days_ahead = 7
            next_monday = now.date() + timedelta(days=days_ahead)
            return datetime.combine(next_monday, datetime.min.time())

        else:
            raise ValueError(f"不支持的时间周期: {timeframe}")

    @staticmethod
    def get_now_time():
        return datetime.now() + timedelta(hours=8)

    @staticmethod
    def compute_stop_loss_price(side, kd, entry_price=None, timeframe="1m"):
        """
        获取止损价格

        :param side: 交易方向，'long' 或 'short'
        :param kd: K线数据对象
        :param entry_price: 入场价格
        :param timeframe: 时间框架，例如 '15m', '1h', '4h'
        :return:
        """
        # 将timeframe降级在提高数量，防止插针数据
        if timeframe == '1w':
            timeframe = '1d'
        elif timeframe == '1d':
            timeframe = '4h'
        elif timeframe == '4h':
            timeframe = '1h'
        elif timeframe == '1h':
            timeframe = '30m'
        elif timeframe == '30m':
            timeframe = '15m'
        elif timeframe == '15m':
            timeframe = '5m'
        elif timeframe == '5m':
            timeframe = '3m'
        elif timeframe == '3m':
            timeframe = '1m'

        if len(getattr(kd, 'df_{}'.format(timeframe))) < 100:
            kd.update_kdata(timeframe, 100)

        # 加载参数
        atr = kd.get_atr(timeframe, 14)
        if not entry_price:
            entry_price = kd.m.get_now_price()

        # 计算出价格A - 最大最小值和ATR的值
        max_price_close = kd.get_kdata_max_price(timeframe, 0, 96, "close")
        max_price_high = kd.get_kdata_max_price(timeframe, 0, 96, "high")
        min_price_close = kd.get_kdata_min_price(timeframe, 0, 96, "close")
        min_price_low = kd.get_kdata_min_price(timeframe, 0, 96, "low")
        max_price_close_2 = kd.get_kdata_max_price(timeframe, 0, 20, "close")
        min_price_close_2 = kd.get_kdata_min_price(timeframe, 0, 20, "close")
        atr_rate = 1.6
        if side == 'long' and min_price_close == min_price_close_2:
            atr_rate = 4.6
        elif side == 'short' and max_price_close == max_price_close_2:
            atr_rate = 4.6
        atr_value = atr * atr_rate
        if side == 'long':
            stop_loss_price_a = (min_price_close + min_price_low) / 2 - atr_value
        else:
            stop_loss_price_a = (max_price_close + max_price_high) / 2 + atr_value

        # 计算止损价格B - ATR5.9倍止损点位
        if side == 'long':
            stop_loss_price_b = entry_price - 6.8 * atr
        else:
            stop_loss_price_b = entry_price + 6.8 * atr

        # 如果是多头，取更大的值，如果是空头，取更小的值
        if side == 'long':
            stop_loss_price = max(stop_loss_price_a, stop_loss_price_b)
        else:
            stop_loss_price = min(stop_loss_price_a, stop_loss_price_b)

        return stop_loss_price

    @staticmethod
    def update_execute_stop_price(side, price_data, execute_price=None, stop_loss_price=None, stop_win_price=None):
        """
            更新执行止损止盈价格
            多头
                - 执行价格： 越小越好，盈亏比更好
                - 止损价格： 越大越好，盈亏比更好
                - 止盈价格： 越大越好，盈亏比更好
            空头
                - 执行价格： 越大越好，盈亏比更好
                - 止损价格： 越小越好，盈亏比更好
                - 止盈价格： 越小越好，盈亏比更好
            1. 处理execute_price
            2. 处理stop_loss_price
            3. 处理stop_win_price
            :param side:
            :param price_data:
            :param execute_price:
            :param stop_loss_price:
            :param stop_win_price:
            :return:
            """
        # 1. 处理执行价格
        if execute_price:
            if price_data['execute_price'] != 0:
                # 多头执行价格越小越好，空头执行价格越大越好
                func = min if side == 'long' else max
                price_data['execute_price'] = func(price_data['execute_price'], execute_price)
            else:
                price_data['execute_price'] = execute_price

        # 2. 处理止损价格
        if stop_loss_price:
            if price_data['stop_loss_price'] != 0:
                # 多头止损价格越大越好，空头止损价格越小越好
                func = max if side == 'long' else min
                price_data['stop_loss_price'] = func(price_data['stop_loss_price'], stop_loss_price)
            else:
                price_data['stop_loss_price'] = stop_loss_price

        # 3. 处理止盈价格
        if stop_win_price:
            if price_data['stop_win_price'] != 0:
                # 多头止盈价格越大越好，空头止盈价格越小越好
                func = max if side == 'long' else min
                price_data['stop_win_price'] = func(price_data['stop_win_price'], stop_win_price)
            else:
                price_data['stop_win_price'] = stop_win_price

    def smart_update_stop_loss_price(self, side, price_data, timeframe, kd, pnl_rate=2):
        """
        智能更新止损价格，优先级最高，因为考虑到风险交易，那么止损价格一定是优先获取的
        盈亏比 = (止盈价格 - 执行价格) / (执行价格 - 止损价格)
        止盈价格 = 盈亏比 * (执行价格 - 止损价格) + 执行价格
        执行价格 = (止盈价格 + 盈亏比 * 止损价格) / (1 + 盈亏比)
        止损价格 = 执行价格 * (1 + 盈亏比) - 止盈价格 / 盈亏比

        :param side:
        :param price_data:
        :param timeframe:
        :param kd:
        :param pnl_rate: 盈亏比
        :return:
        """
        #  如果存在止盈和执行价格，直接通过盈亏比计算止损价格
        if price_data['execute_price'] > 0 and price_data['stop_win_price'] > 0:
            # 止损价格 = 执行价格 * (1 + 盈亏比) - 止盈价格 / 盈亏比
            smart_stop_loss_price = price_data['execute_price'] * (1 + pnl_rate) - price_data[
                'stop_win_price'] / pnl_rate
            self.update_execute_stop_price(side, price_data, stop_loss_price=smart_stop_loss_price)

        execute_price = price_data['execute_price']

        # 计算止损
        stop_loss_price = 0
        stop_loss_price_1 = self.compute_stop_loss_price(side, kd, timeframe=timeframe)
        atr = kd.get_atr(timeframe)
        if execute_price > 0 and side == 'long':
            # 止损价格 = 执行价格 * (1 + 盈亏比) - 止盈价格 / 盈亏比
            stop_loss_price_2 = price_data['execute_price'] - 2.5 * atr
            # 止损价格取更小的值
            stop_loss_price = min(stop_loss_price_1, stop_loss_price_2)
        elif execute_price > 0 and side == 'short':
            stop_loss_price_2 = price_data['execute_price'] + 2.5 * atr
            stop_loss_price = max(stop_loss_price_1, stop_loss_price_2)
        self.update_execute_stop_price(side, price_data, stop_loss_price=stop_loss_price)

    def smart_update_execute_price(self, side, price_data, timeframe, kd, pnl_rate=2):
        """
        智能计算执行价格
        不同维度取计算execute_price
        执行价格 = (止盈价格 + 盈亏比 * 止损价格) / (1 + 盈亏比)
        如果有止盈和止损价格则优先止盈盈亏比来进行计算执行价格
        如果没有则使用下面的维度来进行计算
        - 多头
            均线以上，使用EMA5为入场价格
            均线以下，20日内最大最小值，0.618的位置取值为入场价格
        - 空头
            均线以下，使用EMA5为入场价格
            均线以下，20日内最大最小值，0.618的位置取值为入场价格


        多头 - execute_price 越小越好，收益率越高
        空头 - execute_price 越大越好，收益率越高

        :param side:
        :param price_data:
        :param timeframe:
        :param kd:
        :param pnl_rate: 盈亏比
        :return:
        """

        # 1.有止盈止损价格 - 使用盈亏比来计算入场价格
        if price_data['stop_win_price'] > 0 and price_data['stop_loss_price'] > 0:
            execute_price = (price_data['stop_win_price'] + pnl_rate * price_data[
                'stop_loss_price']) / (1 + pnl_rate)
            self.update_execute_stop_price(side, price_data, execute_price=execute_price)
            return price_data

        # 2. 止盈止损价格不全 - 使用均线和最大最小值维度来计算入场价格
        # 2.1 初始化一些kd数据
        ema5 = kd.get_ema(timeframe, 15)
        max_price = kd.get_kdata_max_price(timeframe, 0, 20)
        min_price = kd.get_kdata_min_price(timeframe, 0, 20)
        high_price = kd.get_high(timeframe, 0)
        low_price = kd.get_low(timeframe, 0)
        now_price = kd.m.get_now_price()
        if side == 'long' and now_price > ema5:
            # 2.2 多头 - 均线以上，使用EMA5为入场价格
            execute_price = ema5
        elif side == 'long' and now_price < ema5:
            # 2.3 多头 - 均线以下，20日内最大最小值，0.618的位置取值为入场价格
            execute_price = min_price + (max_price - min_price) * 0.618
            execute_price = min(execute_price, (now_price + low_price) / 2)
        elif side == 'short' and now_price < ema5:
            # 2.4 空头 - 均线以下，使用EMA5为入场价格
            execute_price = ema5
        elif side == 'short' and now_price > ema5:
            # 2.5 空头 - 均线以上，20日内最大最小值，0.618的位置取值为入场价格
            execute_price = max_price - (max_price - min_price) * 0.618
            execute_price = max(execute_price, (now_price + high_price) / 2)
        else:
            execute_price = price_data['execute_price']

        # 3. 更新一下执行价格
        self.update_execute_stop_price(side, price_data, execute_price=execute_price)

    def smart_update_stop_win_price(self, side, price_data, timeframe, kd, pnl_rate=2):
        """
        智能更新止盈价格
        存在止损和执行价格直接计算
        不存在止损和执行价格，使用下面的维度来计算
        维度1：N天的最大最小值
        维度2：有执行价的话，使用执行价+-2倍ATR值
        维度3：EMA99的值
          :param side:
        :param price_data:
        :param timeframe:
        :param kd:
        :param pnl_rate: 盈亏比
        """

        # 1.有止损和执行价格 - 使用盈亏比来计算止盈价格
        if price_data['execute_price'] > 0 and price_data['stop_loss_price'] > 0:
            # 止盈价格 = 盈亏比 * (执行价格 - 止损价格) + 执行价格
            smart_stop_win_price = pnl_rate * (price_data['execute_price'] - price_data[
                'stop_loss_price']) + price_data['execute_price']
            self.update_execute_stop_price(side, price_data, stop_win_price=smart_stop_win_price)
            return

        # 2. 没有执行和止盈价格
        # 2.1 初始化一些kd数据
        ema99 = kd.get_ema(timeframe, 99)
        max_price = kd.get_kdata_max_price(timeframe, 0, 20)
        min_price = kd.get_kdata_min_price(timeframe, 0, 20)
        atr = kd.get_atr(timeframe)
        high_price = kd.get_high(timeframe, 0)
        low_price = kd.get_low(timeframe, 0)
        now_price = kd.m.get_now_price()
        if side == 'long' and now_price < ema99:
            # 2.2 多头 - 均线以下，使用EMA99为止盈价格
            stop_win_price = ema99
        elif side == 'long' and now_price > ema99 and price_data['execute_price'] > 0:
            # 2.3 多头 - 均线以上，使用执行价+2倍ATR值
            stop_win_price = price_data['execute_price'] + 2 * atr
        elif side == 'short' and now_price > ema99:
            # 2.4 空头 - 均线以上，使用EMA99为止盈价格
            stop_win_price = ema99
        elif side == 'short' and now_price < ema99 and price_data['execute_price'] > 0:
            # 2.5 空头 - 均线以下，使用执行价-2倍ATR值
            stop_win_price = price_data['execute_price'] - 2 * atr
        else:
            if self.side == 'long':
                stop_win_price = max(max_price, ema99, high_price)
            else:
                stop_win_price = min(min_price, ema99, low_price)

        self.update_execute_stop_price(side, price_data, stop_win_price=stop_win_price)
