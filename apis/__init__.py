import ccxt
from .market import Market
from .user import User
from .order import Order
from .kdata import KData
from .compute import Compute


class CcxtApis(object):
    def __init__(self, exchange_name, api_key, api_secret, *args, **kwargs):
        """
        初始化ccxt交易所对象
        :param exchange_name:
        :param api_key:
        :param api_secret:
        :param symbol:
        """
        exchange_class = getattr(ccxt, exchange_name)
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'requests_trust_env': True
        })
        # self.exchange.load_markets()
        self.side = kwargs.get('side')

    def market(self, symbol, *args, **kwargs):
        """
        获取市场
        :return:
        """
        side = kwargs.get('side')
        if not side:
            side = self.side
        return Market(symbol=symbol, exchange=self.exchange, side=side, *args, **kwargs)

    def user(self, symbol, *args, **kwargs):
        """
        获取用户仓位等相关数据
        :return:
        """
        side = kwargs.get('side')
        if not side:
            side = self.side
        return User(symbol=symbol, exchange=self.exchange, side=side, *args, **kwargs)

    def order(self, symbol, *args, **kwargs):
        """
        挂单相关的
        :param symbol:
        :param args:
        :param kwargs:
        :return:
        """
        side = kwargs.get('side')
        if not side:
            side = self.side
        return Order(symbol=symbol, exchange=self.exchange, side=side, *args, **kwargs)

    def kdata(self, symbol, *args, **kwargs):
        """
        挂单相关的
        :param symbol:
        :param args:
        :param kwargs:
        :return:
        """
        return KData(symbol=symbol, exchange=self.exchange, *args, **kwargs)

    def compute(self, symbol, *args, **kwargs):
        """
        挂单相关的
        :param symbol:
        :param args:
        :param kwargs:
        :return:
        """
        return Compute(symbol=symbol, exchange=self.exchange, *args, **kwargs)


if __name__ == '__main__':
    CcxtApis()
