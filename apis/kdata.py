from .base import BaseFunc
import talib
import pandas as pd
from .market import Market


class KData(BaseFunc):
    def __init__(self, symbol, exchange, *args, **kwargs):
        """
        :param symbol:
        :param exchange:
        """
        super(KData, self).__init__(symbol, exchange, *args, **kwargs)
        self.m = Market(symbol=symbol, exchange=self.exchange, *args, **kwargs)
        self.df_1m = []
        self.df_3m = []
        self.df_5m = []
        self.df_15m = []
        self.df_30m = []
        self.df_1h = []
        self.df_4h = []
        self.df_1d = []
        self.df_1w = []

    def _verify_k_time(self, k_times):
        """
        验证k_time是否满足
        :param k_times:
        :return:
        """
        if type(k_times) is str:
            k_times = [k_times]

        for k_time in k_times:
            try:
                getattr(self, 'df_{}'.format(k_time))
            except Exception as e:
                return False

        return True

    def get_df(self, k_time):
        """
        获取对应的df数据
        :param k_time:
        :return:
        """
        df = getattr(self, 'df_{}'.format(k_time))
        return df

    @BaseFunc.while_loop
    def update_kdata(self, k_time, k_num=30):
        """
        更新k线数据
        :param k_num: K线数量
        :param k_time: K线周期
        :return:
        """
        if not self._verify_k_time(k_time):
            raise ValueError("{} - update_kdata-验证K线失败".format(self.symbol))

        k_data_infos = self.handle('fetch_ohlcv', symbol=self.symbol, timeframe=k_time, limit=k_num)

        if not k_data_infos:
            return False

        # 定义列名
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

        # 创建 DataFrame
        df = pd.DataFrame(k_data_infos, columns=columns)

        # 将时间戳列转换为 datetime 类型
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        setattr(self, 'df_{}'.format(k_time), df)
        return True

    def update_kdatas(self, k_times, k_num=30):
        """
        更新多个K线数据
        :param k_times:
        :param k_num:
        :return:
        """
        if not self._verify_k_time(k_times):
            return False

        for k_time in k_times:
            if not self.update_kdata(k_time, k_num):
                return False

        return True

    def _filter_kdata_price_for_ohlcv(self, k_time, ref=0, max_ref=0, ohlcv='close'):
        """
        过滤df
        :param k_time:
        :param ref:
        :param max_ref:
        :param ohlcv:
        :return:
        """
        if not self._verify_k_time(k_time):
            return False

        if ohlcv not in ['open', 'high', 'low', 'close', 'volume']:
            return False

        df = getattr(self, 'df_{}'.format(k_time))
        if ref > 0:
            if max_ref > 0:
                df = df.iloc[-ref - max_ref: -ref]
            else:
                df = df.iloc[:-ref]
        else:
            if max_ref > 0:
                df = df.iloc[-max_ref:]

        return df[ohlcv]

    def get_kdata_max_price(self, k_time, ref=0, max_ref=0, ohlcv='high'):
        """
        获取指定k_data指定维度的最大值, ref=0, max_ref=5, 就是取前5根包括最新一根K线的最大值
        :param ref: 前几位值，默认就是0就是当前的值
        :param max_ref: 最大取ref几个值，0就是默认所有
        :param k_time:
        :param ohlcv:
        :return:
        """
        df = self._filter_kdata_price_for_ohlcv(k_time, ref, max_ref, ohlcv)
        if type(df) is bool:
            return False

        return df.max()

    def get_kdata_min_price(self, k_time, ref=0, max_ref=0, ohlcv='low'):
        """
        获取指定k_data指定维度的最小值, ref=0, max_ref=5, 就是取前5根包括最新一根K线的最小值
        :param ref: 前几位值，默认就是0就是当前的值
        :param max_ref: 最大取ref几个值，0就是默认所有
        :param k_time:
        :param ohlcv:
        :return:
        """
        df = self._filter_kdata_price_for_ohlcv(k_time, ref, max_ref, ohlcv)
        if type(df) is bool:
            return False

        return df.min()

    def get_open(self, k_time, ref=0):
        """
        获取开盘价格
        :param k_time:
        :param ref:
        :return:
        """
        df = self._filter_kdata_price_for_ohlcv(k_time, ref, 1, 'open')
        if type(df) is bool:
            return False

        return df.iloc[0]

    def get_close(self, k_time, ref=0):
        """
        获取收盘价格
        :param k_time:
        :param ref:
        :return:
        """
        df = self._filter_kdata_price_for_ohlcv(k_time, ref, 1, 'close')
        if type(df) is bool:
            return False

        return df.iloc[0]

    def get_high(self, k_time, ref=0):
        """
        获取最高价格
        :param k_time:
        :param ref:
        :return:
        """
        df = self._filter_kdata_price_for_ohlcv(k_time, ref, 1, 'high')
        if type(df) is bool:
            return False

        return df.iloc[0]

    def get_low(self, k_time, ref=0):
        """
        获取最低价格
        :param k_time:
        :param ref:
        :return:
        """
        df = self._filter_kdata_price_for_ohlcv(k_time, ref, 1, 'low')
        if type(df) is bool:
            return False

        return df.iloc[0]

    def get_volume(self, k_time, ref=0):
        """
        获取成交量
        :param k_time:
        :param ref:
        :return:
        """
        df = self._filter_kdata_price_for_ohlcv(k_time, ref, 1, 'volume')
        if type(df) is bool:
            return False

        return df.iloc[0]

    # 获取技术指标
    def auto_update_kdata(self, k_time, limit):
        """
        根据limit值来自动进行更新Kdata
        :param k_time:
        :param limit:
        :return:
        """
        df = getattr(self, 'df_{}'.format(k_time))
        if len(df) < limit:
            self.update_kdata(k_time, limit)

    def get_sma(self, k_time, limit=20, ref=0):
        """
        获取sma数据
        :param k_time:
        :param limit:
        :param ref:
        :return:
        """
        if not self._verify_k_time(k_time):
            return False

        self.auto_update_kdata(k_time, limit + 10)

        sma = talib.SMA(self._filter_kdata_price_for_ohlcv(k_time, ohlcv='close'), limit)
        if ref >= 0:
            return sma.iloc[-ref - 1]
        return sma

    def get_ema(self, k_time, limit=20, ref=0):
        """
        获取ema数据
        :param k_time:
        :param limit:
        :param ref:
        :return:
        """
        if not self._verify_k_time(k_time):
            return False

        self.auto_update_kdata(k_time, limit * 3)

        sma = talib.EMA(self._filter_kdata_price_for_ohlcv(k_time, ohlcv='close'), limit)
        if ref >= 0:
            return sma.iloc[-ref - 1]
        return sma

    def get_atr(self, k_time, limit=14, ref=0):
        """
        获取ATR的值
        :param k_time:
        :param limit:
        :param ref:
        :return:
        """
        if not self._verify_k_time(k_time):
            return False

        self.auto_update_kdata(k_time, limit * 10)

        atr = talib.ATR(self._filter_kdata_price_for_ohlcv(k_time, ohlcv='high'),
                        self._filter_kdata_price_for_ohlcv(k_time, ohlcv='low'),
                        self._filter_kdata_price_for_ohlcv(k_time, ohlcv='close'),
                        timeperiod=limit)

        if ref >= 0:
            return atr.iloc[-ref - 1]
        return atr
