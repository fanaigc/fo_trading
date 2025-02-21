import logging
import time


class BaseFunc(object):
    def __init__(self, symbol, exchange, *args, **kwargs):
        """
        :param symbol:
        :param exchange:
        """
        self.exchange = exchange
        self.symbol = symbol
        self.side = kwargs.get('side')
        if self.side:
            if self.side.lower() not in ['long', 'short']:
                self.side = None

        if len(self.symbol.split(':')) == 1:
            self.is_future = False
        else:
            self.is_future = True

        # self.u = self.exchange.user(self.symbol)
        # self.o = self.exchange.order(self.symbol)

    def handle(self, func, *args, **kwargs):
        """
        批量化处理
        :param func:
        :param args:
        :param kwargs:
        :return:
        """
        try:
            info = getattr(self.exchange, func)(*args, **kwargs)
            return info
        except Exception as e:
            symbol = getattr(self, 'symbol', None)
            if not ('GET' in str(e) and 'http' in str(e)):
                logging.error("{} - 执行{}时出现了错误: {}".format(symbol, func, e))
            return False

    @staticmethod
    def while_loop(func):
        def wrapper(*args, **kwargs):
            s = 0
            symbol = ''
            if args:
                try:
                    symbol = args[0].symbol
                except Exception as e:
                    pass
            while True:
                time.sleep(s)
                s += 1
                if s > 10:
                    s += s
                    logging.info("{} - 多次尝试执行{}失败，请检查原因!".format(symbol, func.__name__))
                result = func(*args, **kwargs)
                if result:
                    return result

        return wrapper
