from .base import BaseFunc
from .market import Market


class User(BaseFunc):
    def __init__(self, symbol, exchange, *args, **kwargs):
        super(User, self).__init__(symbol, exchange, *args, **kwargs)
        self.m = Market(symbol=symbol, exchange=self.exchange, *args, **kwargs)

    @BaseFunc.while_loop
    def _get_balance(self, exchange_type='swap'):
        """
        获取账户余额
        不同交易所可能有不同的方法，需要注意
        :return:
        """
        balance_info = self.handle('fetch_balance', {
            'type': exchange_type
        })
        if not balance_info:
            return False
        return balance_info

    def get_balance(self, exchange_type='swap', symbol=None, available=False):
        """
        获取可用的余额
        :param available:
        :param exchange_type:
        :param symbol:
        :return:
        """
        balance_info = self._get_balance(exchange_type)
        # 进行具体的数据过滤
        if symbol:
            symbol = symbol.split('/')[0].upper()
            balance_info = balance_info.get(symbol)
        else:
            balance_info = balance_info.get('USDT')

        # 如果没有数据则直接返回
        if not balance_info:
            return False

        # 判断是否是想获
        if available:
            return balance_info['free']
        return balance_info['total']

    @BaseFunc.while_loop
    def get_positions(self):
        """
        获取仓位信息
        :return:
        """
        if self.exchange.id == 'binance':
            position_infos = self.handle('fetch_account_positions', [self.symbol])
        else:
            position_infos = self.handle('fetch_position', self.symbol)

        return self._parse_positions_info(position_infos)

    def get_position_amount(self, side=None):
        """
        获取仓位数量
        :param side:
        :return:
        """
        if not self.is_future:
            return self.get_balance('spot', self.symbol)

        position_infos = self.get_positions()
        if not position_infos:
            return 0
        if side not in ['long', 'short']:
            return False

        if not position_infos[side]:
            return 0

        return abs(position_infos[side]['amount'])

    def get_position_value(self, side=None):
        """
        获取仓位价值
        :param side:
        :return:
        """
        if not self.is_future:
            return self.get_balance('spot', self.symbol) * self.m.get_now_price()

        position_infos = self.get_positions()
        if not position_infos:
            return 0
        if side not in ['long', 'short']:
            return False

        if not position_infos[side]:
            return 0

        return float(position_infos[side]['value'])

    def _get_binance_last_close_pnl(self, side):
        """
        获取binance最后交易的Pnl收益
        :param side:
        :return:
        """
        trades = self.handle('fetch_my_trades', self.symbol, limit=120)
        if not trades:
            return 0

        trades.reverse()

        pnl = 0
        for trade in trades:
            info = trade['info']
            if info['positionSide'] == side.upper() and side == 'long':
                if info['side'] == 'BUY':
                    break
                pnl += float(info['realizedPnl'])

            if info['positionSide'] == side.upper() and side == 'short':
                if info['side'] == 'SELL':
                    break
                pnl += float(info['realizedPnl'])

        return pnl

    def _parse_positions_info(self, positions_infos):
        """
        解析positions_info的信息
        :param positions_info:
        :return:
        """
        long_positions_info = {}
        short_positions_info = {}

        if self.exchange.id == 'gate':
            if not positions_infos.get('info'):
                return False
            positions_info = positions_infos['info']

            for position in positions_info:
                mode = position['mode']
                value = position['value']
                last_close_pnl = position['last_close_pnl']
                amount = float(position['size']) * self.m.amount_size
                avg_buy_price = position['entry_price']
                if mode == 'dual_long':
                    long_positions_info['value'] = value
                    long_positions_info['last_close_pnl'] = last_close_pnl
                    long_positions_info['amount'] = amount
                    long_positions_info['avg_buy_price'] = avg_buy_price
                elif mode == 'dual_short':
                    short_positions_info['value'] = value
                    short_positions_info['last_close_pnl'] = last_close_pnl
                    short_positions_info['amount'] = amount
                    short_positions_info['avg_buy_price'] = avg_buy_price

        if self.exchange.id == 'binance':
            for position in positions_infos:
                side = position['side']
                value = position['notional']
                amount = position['contracts']
                avg_buy_price = position['entryPrice']
                if side == 'long':
                    long_positions_info['value'] = value
                    long_positions_info['last_close_pnl'] = 0
                    long_positions_info['amount'] = amount
                    long_positions_info['avg_buy_price'] = avg_buy_price
                if side == 'short':
                    short_positions_info['value'] = value
                    short_positions_info['last_close_pnl'] = 0
                    short_positions_info['amount'] = amount
                    short_positions_info['avg_buy_price'] = avg_buy_price

        return {
            'long': long_positions_info,
            'short': short_positions_info
        }

    def get_position_avg_buy_price(self, side):
        """
        获取平均买入价格
        :param side:
        :return:
        """
        position_infos = self.get_positions()
        if side not in ['long', 'short']:
            return False

        if not position_infos[side]:
            return 0

        return float(position_infos[side]['avg_buy_price'])

    def get_position_last_close_pnl(self, side):
        """
        获取上次交易结束的收益
        :param side:
        :return:
        """
        if self.exchange.id == 'binance':
            return self._get_binance_last_close_pnl(side)

        position_infos = self.get_positions()
        if side not in ['long', 'short']:
            return False

        if not position_infos[side]:
            return 0

        return position_infos[side]['last_close_pnl']

    # @BaseFunc.while_loop
    # def get_balance(self, exchange_type='swap'):
    #     """
    #     获取账户余额
    #     不同交易所可能有不同的方法，需要注意
    #     :return:
    #     """
    #     balance_info = self.handle('fetch_balance', {
    #         'type': exchange_type
    #     })
    #     if not balance_info:
    #         return False
    #     return balance_info
