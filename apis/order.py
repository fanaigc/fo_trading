import logging

from .base import BaseFunc
from .market import Market


class Order(BaseFunc):
    def __init__(self, symbol, exchange, *args, **kwargs):
        super(Order, self).__init__(symbol, exchange, *args, **kwargs)
        self.m = Market(symbol=symbol, exchange=self.exchange, *args, **kwargs)

    def _covert_amount(self, amount):
        return self.handle('amount_to_precision', self.symbol, round(amount / self.m.amount_size, 15))

    def _format_params(self, side=None, mode=None):
        """
        格式化params
        :param side:
        :param mode:
        :return:
        """
        params = {}

        if self.exchange.id == 'binance':
            if side == 'long':
                params['positionSide'] = 'LONG'
            elif side == 'short':
                params['positionSide'] = 'SHORT'

        if self.exchange.id == 'gate':
            if mode:
                # 不同的运行模式，如果PO
                params['timeInForce'] = mode

        return params

    def _get_open_order_params(self, side=None, mode=None):
        """
        根据不同的方法和交易所组件不同的params
        :return:
        """
        params = self._format_params(side=side, mode=mode)

        if self.exchange.id == 'binance':
            pass

        if self.exchange.id == 'gate':
            params['reduceOnly'] = False

        return params

    def _get_close_order_params(self, side=None, mode=None):
        """
        获取平仓的params
        :param side:
        :param mode:
        :return:
        """
        params = self._format_params(side=side, mode=mode)

        if self.exchange.id == 'binance':
            pass

        if self.exchange.id == 'gate':
            params['reduceOnly'] = True

        return params

    def _get_stop_order_params(self, side=None, price=None):
        params = {}

        if self.exchange.id == 'gate':
            if not all([side, price]):
                raise ValueError('缺少参数：side、price')

            params['initial'] = {
                "contract": self.exchange.market(symbol=self.symbol)['id'],
                "size": 0,
                "price": '0',
                'tif': 'ioc',
                "auto_size": 'close_{}'.format(side),
                'reduce_only': True
            }

            now_price = self.m.get_now_price()
            if now_price < price:
                rule = 1
            elif now_price > price:
                rule = 2
            else:
                return False

            params['trigger'] = {
                "strategy_type": 0,
                "price_type": 0,
                "price": self.exchange.price_to_precision(self.symbol, price),
                "rule": rule,
                "expiration": 86400
            }
            params['order_type'] = 'close-{}-position'.format(side)
            params['close'] = True

        if self.exchange.id == 'binance':
            if not all([side, price]):
                raise ValueError('缺少参数：side、price')

            now_price = self.m.get_now_price()
            if side == 'long':
                if now_price < price:
                    # price是止盈价格
                    params['takeProfitPrice'] = price

                elif now_price > price:
                    params['stopLossPrice'] = price

                else:
                    return False

            elif side == 'short':
                if now_price < price:
                    params['stopLossPrice'] = price

                elif now_price > price:
                    params['takeProfitPrice'] = price

                else:
                    return False
            params['positionSide'] = side.upper()
            params['closePosition'] = True

        return params

    def _get_cancel_stop_order_params(self):
        """
        获取取消停止订单的params
        :return:
        """
        params = {}
        if self.exchange.id == 'gate':
            params['stop'] = True

        return params

    def open_order(self, side, amount, price=None, covert_amount=True, mode=None, log=False):
        """
        开仓多头
        :param covert_amount: 是否转换amount
        :param side: 开仓方向,
        :param amount: 开仓数量（size）
        :param price: 开仓价格
        :param mode:
            GTC-最好的成交方式，如果价格低于限定价格则直接买进 default;
            IOC-立即成交的成交，不然则不成交;
            PO-最优质的成交，如果价格低于挂单价则不进行交易;
        :param log: 是否输出日志
        :return:
        """
        if covert_amount:
            amount = self._covert_amount(amount)
            if not amount:
                return False
        if price:
            price = self.m.get_can_order_price(price)

        # 1. 根据价格来判断是市价还是限价
        order_type = 'limit'
        if not price:
            order_type = 'market'

        # 2. 进行转化多空
        if not self.is_future:
            side = 'long'

        if side == 'long':
            # side = 'buy'
            side_str = '做多'
        elif side == 'short':
            # side = 'sell'
            side_str = '做空'
        else:
            raise ValueError("错误的交易参数")

        # 3. 组成order_dict
        order_data = {
            'symbol': self.symbol,
            'type': order_type,
            # 'side': side,
            'side': 'buy' if side == 'long' else 'sell',
            'amount': amount,
            'price': price,
            'params': self._get_open_order_params(side=side, mode=mode) if self.is_future else {}
        }
        order_info = self.exchange.create_order(**order_data)
        # order_info = self.handle('create_order', **order_data)

        if not all([order_info, log]):
            return order_info

        status = order_info.get('status')
        average = order_info.get('average')
        if status == 'open':
            # 挂单
            logging.info("{} - 开仓 - 在${}挂单{}：{}".format(self.symbol, price, side_str, amount))
        elif status == 'closed':
            # 完全成交
            logging.info("{} - 开仓 - 以${}成功{}: {}".format(self.symbol, average, side_str, amount))

        return order_info

    def close_order(self, side, amount, price=None, covert_amount=True, mode=None, log=False):
        """
        平仓交易
        :param covert_amount:
        :param log: 是否输出日志
        :param mode:
            默认GTC-最好的成交方式，如果价格低于限定价格则直接买进，
            IOC-立即成交的成交，不然则不成交，
            PO-最优质的成交，如果价格低于挂单价则不进行交易
        :param side: long-多头， short-空头
        :param amount: 交易数量
        :param price:
        :return:
        """
        if covert_amount:
            amount = self._covert_amount(amount)
            if not amount:
                return False

        if price:
            price = self.m.get_can_order_price(price)

        # 1. 根据价格来判断是市价还是限价
        order_type = 'limit'
        if not price:
            order_type = 'market'

        # 2. 进行转化多空
        if not self.is_future:
            side = 'long'

        if side == 'long':
            # side = 'sell'
            side_str = '平多'
        elif side == 'short':
            # side = 'buy'
            side_str = '平空'
        else:
            raise ValueError("错误的交易参数")

        order_data = {
            'symbol': self.symbol,
            'type': order_type,
            'side': 'sell' if side == 'long' else 'buy',
            'amount': amount,
            'price': price,
            'params': self._get_close_order_params(side=side, mode=mode) if self.is_future else {}
        }

        order_info = self.handle('create_order', **order_data)

        if not all([order_info, log]):
            return order_info

        status = order_info.get('status')
        average = order_info.get('average')
        if status == 'open':
            # 挂单
            logging.info("{} - 平仓 - 在${}挂单{}：{}".format(self.symbol, price, side_str, amount))
        elif status == 'closed':
            # 完全成交
            logging.info("{} - 平仓 - 以${}成功{}: {}".format(self.symbol, average, side_str, amount))

        return order_info

    def stop_order_for_price(self, side, price, log=False):
        """
        指定价格进行系统止盈止损
        :param log:
        :param side:
        :param price:
        :return:
        """
        if price:
            price = self.m.get_can_order_price(price)

        # 1. 先判断一下是否在price的价格已经有了止损，如果已经有了就不需要进行操作了
        stop_price = self.get_stop_loss_price(side)
        if stop_price == price:
            # 已经存在对应的止损订单，什么都不需要做
            return

        # 取消止损订单后在进行挂单
        self.cancel_stop_loss_order(side)

        # 判断一下挂单止损价格是否已经满足强平价格，满足直接强平
        # now_price = self.m.get_now_price()
        # if side == 'long':
        #     if now_price >= price:
        #         return self.close_order(side, self.m.get_can_close_amount(), price=price, log=log)

        # 1. 进行转化多空
        if side == 'long':
            order_side = 'sell'
            side_str = '多头'
        elif side == 'short':
            order_side = 'buy'
            side_str = '空头'
        else:
            raise ValueError("错误的交易参数")

        params = self._get_stop_order_params(side, price)
        if not params:
            return False

        order_data = {
            'symbol': self.symbol,
            'type': 'limit' if self.exchange.id == 'gate' else 'market',
            'side': order_side,
            'amount': 0,
            'price': price,
            'params': params
        }
        order_info = self.handle('create_order', **order_data)

        if not all([order_info, log]):
            return order_info

        logging.info("{} - 止损 - {}在${}挂单平仓".format(self.symbol, side_str, price))

        return order_info

    def auto_open_order(self, side, amount, num=10, mode=None, log=False):
        """
        自动开单交易
        :param log:
        :param amount: 开仓的amount
        :param side: long-多头， short-空头
        :param num:  max-10，自动交易挂单的数量
        :param mode: 默认None就是会按GTC成交，如果PO的话就会只进行挂单
        :return:
        """
        # 1. 字段初始化
        try:
            num = int(num)
            if num >= 10:
                num = 10
        except Exception:
            logging.info("{} - auto_open_order-num错误！".format(self.symbol))
            return False

        if side not in ['long', 'short']:
            logging.info("{} - auto_open_order-side错误！".format(self.symbol))
            return False

        # 进行amount分割计算
        amount = self._covert_amount(amount)
        if not amount:
            return False

        # 计算amount
        amount = float(amount)
        unit_amount = amount / num
        unit_amount = max(self.m.get_min_amount(), unit_amount)
        unit_amount = self.exchange.amount_to_precision(self.symbol, unit_amount)
        unit_amount = float(unit_amount)

        #  获取订单簿
        if side == 'long':
            order_list = self.m.get_order_books(side='buy')
        elif side == 'short':
            order_list = self.m.get_order_books(side='sell')
        else:
            return False

        if not order_list:
            return False

        order_list = order_list[:num]
        now_order_amount = 0
        for order in order_list:
            order_amount = unit_amount
            if now_order_amount == 0 and amount - unit_amount * num > 0:
                # 因为size，通过amount_to_precision计算会进行去除小数位，那么就会有一些细微的差值，都在第一次进行交易
                order_amount = order_amount + (amount - unit_amount * num)

            self.open_order(side=side, amount=order_amount, price=order[0], covert_amount=False, mode=mode, log=log)

            now_order_amount += unit_amount
            if now_order_amount >= amount:
                return True

    def auto_close_order(self, side, amount, num=10, mode=None, log=False):
        """
        自动开单交易
        :param log:
        :param amount: 开仓的amount
        :param side: long-多头， short-空头
        :param num:  max-10，自动交易挂单的数量
        :param mode: 默认None就是会按GTC成交，如果PO的话就会只进行挂单
        :return:
        """
        # 1. 字段初始化
        try:
            num = int(num)
            if num >= 10:
                num = 10
        except Exception:
            logging.info("{} - auto_open_order-num错误！".format(self.symbol))
            return False

        if side not in ['long', 'short']:
            logging.info("{} - auto_open_order-side错误！".format(self.symbol))
            return False

        # 进行amount分割计算
        amount = self._covert_amount(amount)
        if not amount:
            return False

        # 计算amount
        amount = float(amount)
        unit_amount = amount / num
        unit_amount = max(self.m.get_min_amount(), unit_amount)
        unit_amount = self.exchange.amount_to_precision(self.symbol, unit_amount)
        unit_amount = float(unit_amount)

        #  获取订单簿
        if side == 'long':
            order_list = self.m.get_order_books(side='sell')
        elif side == 'short':
            order_list = self.m.get_order_books(side='buy')
        else:
            return False

        if not order_list:
            return False

        order_list = order_list[:num]

        now_order_amount = 0
        for order in order_list:
            order_amount = unit_amount
            if now_order_amount == 0 and amount - unit_amount * num > 0:
                # 因为size，通过amount_to_precision计算会进行去除小数位，那么就会有一些细微的差值，都在第一次进行交易
                order_amount = order_amount + (amount - unit_amount * num)
                # logging.info(order_amount)

            self.close_order(side=side, amount=order_amount, price=order[0], covert_amount=False, mode=mode, log=log)

            now_order_amount += unit_amount
            if now_order_amount >= amount:
                return True

    # 取消订单相关的内容
    def _get_orders(self):
        """
        获取订单列表
        :return:
        """
        return self.handle('fetch_open_orders', self.symbol)

    def _get_other_orders(self):
        """
        通过params来获取一些订单信息
        :return:
        """
        if self.exchange.id == 'binance':
            return self._get_orders()
        return self.handle('fetch_closed_orders', symbol=self.symbol, params={
            # 'stop': True,
            'status': 'open',
            'trigger': True
        })

    def _get_open_orders(self, side, price=None):
        """
        获取开仓订单列表
        :param side:
        :param price:
        :return:
        """
        if not self.is_future:
            side = 'long'

        if side not in ['long', 'short']:
            logging.info('{} - _get_open_orders-side错误！'.format(self.symbol))
            return False

        orders_infos = self._get_orders()
        if type(orders_infos) is not list:
            return False

        new_order_infos = []
        for order_info in orders_infos:
            reduce_only = order_info['reduceOnly']
            order_side = order_info['side']
            order_price = order_info['price']

            if reduce_only and self.is_future:
                continue

            if price and price != order_price:
                continue

            if side == 'long' and order_side == 'buy':
                new_order_infos.append(order_info)

            if side == 'short' and order_side == 'sell':
                new_order_infos.append(order_info)
        return new_order_infos

    def _get_close_orders(self, side, price=None):
        """
        获取平仓的订单列表
        :param side:
        :param price:
        :return:
        """
        if not self.is_future:
            side = 'long'

        if side not in ['long', 'short']:
            logging.info('{} - cancel_close_order-side错误！'.format(self.symbol))
            return False

        orders_infos = self._get_orders()
        if type(orders_infos) is not list:
            return False

        new_order_infos = []
        for order_info in orders_infos:
            reduce_only = order_info['reduceOnly']
            order_side = order_info['side']
            order_price = order_info['price']
            amount = order_info['amount']

            if not amount:
                continue

            if not reduce_only and self.is_future:
                continue

            if price and price != order_price:
                continue

            if side == 'long' and order_side == 'sell':
                new_order_infos.append(order_info)

            if side == 'short' and order_side == 'buy':
                new_order_infos.append(order_info)
        return new_order_infos

    def cancel_all_order(self, log=False):
        """
        取消所有的订单
        :return:
        """
        # 针对指定交易所行为
        if self.exchange.id == 'gate':
            self.cancel_all_other_orders(log=log)

        if len(self._get_orders()) == 0:
            return False

        order_infos = self.handle('cancel_all_orders', self.symbol)
        if not all([order_infos, log]):
            return order_infos

        for order_info in order_infos:
            side_str = '多头'
            side = order_info['side']
            reduce_only = order_info['reduceOnly']
            if (side == 'buy' and reduce_only) or (side == 'sell' and not reduce_only):
                side_str = '空头'
            logging.info("{} - 取消 - 成功取消${}的{}挂单".format(self.symbol, order_info['price'], side_str))

        return order_infos

    def get_order_id(self, order_info):
        """
        从order_info中提取Order_id
        :param order_info:
        :return:
        """
        order_id = None
        try:
            order_id = order_info['info']['id']
            # order_id = order_info['info']['orderId']

        except Exception as e:
            pass

        return order_id

    def get_order_id_info(self, order_id, log=False):
        """
        获取order_id的数据
        :param order_id:
        :param log:
        :return:
        """
        order_infos = self.handle('fetch_order', order_id, self.symbol)
        # print(order_infos)
        return order_infos

    def get_order_info_status(self, order_id):
        """
        获取订单状态
        :return:
        """
        order_info = self.get_order_id_info(order_id)
        status = False
        if order_info:
            status = order_info['status']

        return status

    def order_is_closed(self, order_id):
        """
        判断订单是否已经结束
        """
        status = self.get_order_info_status(order_id)
        if not status:
            return True

        if status == 'closed':
            return True
        return False

    def _cancel_order_for_ids(self, cancel_order_ids, params=None):
        """
        取消order_ids
        :param cancel_order_ids:
        :return:
        """
        order_infos = []
        # if self.exchange.has['cancelOrders']:
        #     order_infos = self.handle('cancel_orders', ids=cancel_order_ids, symbol=self.symbol, params=params)
        # else:
        for order_id in cancel_order_ids:
            order_info = self.handle('cancel_order', id=order_id, symbol=self.symbol,
                                     params=params if params else {})
            if order_info:
                order_infos.append(order_info)
        return order_infos

    def cancel_open_order(self, side, price=None, log=False):
        """
        取消开仓的订单
        :param side:
        :param price:
        :param log:
        :return:
        """
        if price:
            price = self.m.get_can_order_price(price)

        cancel_order_infos = self._get_open_orders(side=side, price=price)
        if not cancel_order_infos:
            return False

        cancel_order_ids = []
        for cancel_order in cancel_order_infos:
            cancel_order_ids.append(cancel_order['id'])

        order_infos = self._cancel_order_for_ids(cancel_order_ids)

        if not all([order_infos, log]):
            return order_infos

        for order_info in order_infos:
            side_str = '做多'
            side = order_info['side']
            if side == 'sell':
                side_str = '做空'
            logging.info("{} - 取消 - 成功取消${}的{}挂单".format(self.symbol, order_info['price'], side_str))

        return order_infos

    def cancel_close_order(self, side, price=None, log=False):
        """
        取消开仓的订单
        :param side:
        :param price:
        :param log:
        :return:
        """
        if price:
            price = self.m.get_can_order_price(price)

        cancel_order_infos = self._get_close_orders(side, price)

        cancel_order_ids = []
        for cancel_order in cancel_order_infos:
            cancel_order_ids.append(cancel_order['id'])

        order_infos = self._cancel_order_for_ids(cancel_order_ids)

        if not all([order_infos, log]):
            return order_infos

        for order_info in order_infos:
            side_str = '平多'
            side = order_info['side']
            if side == 'sell':
                side_str = '平空'
            logging.info("{} - 取消 - 成功取消${}的{}挂单".format(self.symbol, order_info['price'], side_str))

        return order_infos

    def cancel_all_other_orders(self, log=False):
        """
        取消所有的
        :param log:
        :return:
        """
        orders_infos = self._get_other_orders()
        if type(orders_infos) is not list:
            return False

        cancel_order_ids = []
        for order_info in orders_infos:
            cancel_order_ids.append(order_info['id'])

        order_infos = self._cancel_order_for_ids(cancel_order_ids,
                                                 params=self._get_cancel_stop_order_params())

        if not all([order_infos, log]):
            return order_infos

        for order_info in order_infos:
            logging.info("{} - 取消 - 成功取消${}的挂单".format(self.symbol, order_info['stopPrice']))

        return order_infos

    def cancel_stop_win_order(self, side, log=False):
        """
        取消止盈的订单
        :param side:
        :param log:
        :return:
        """
        if side not in ['long', 'short']:
            logging.info('{} - cancel_stop_order-side错误！'.format(self.symbol))
            return False

        orders_infos = self._get_other_orders()
        if type(orders_infos) is not list:
            return False

        cancel_order_ids = []
        for order_info in orders_infos:
            if order_info['type'] not in ['market', 'take_profit_market']:
                continue

            order_price = order_info['stopPrice']
            now_price = self.m.get_now_price()
            if side == 'long' and now_price > order_price:
                continue

            if side == 'short' and now_price < order_price:
                continue

            cancel_order_ids.append(order_info['id'])

        order_infos = self._cancel_order_for_ids(cancel_order_ids,
                                                 params=self._get_cancel_stop_order_params())

        if not all([order_infos, log]):
            return order_infos

        for order_info in order_infos:
            side_str = '清仓多头'
            if side == 'short':
                side_str = '清仓空头'
            logging.info("{} - 取消止盈 - 成功取消${}的{}挂单".format(self.symbol, order_info['stopPrice'], side_str))

        return order_infos

    def cancel_stop_loss_order(self, side, log=False):
        """
        取消止盈的订单
        所有市价止盈单都会被取消
        :param side:
        :param log:
        :return:
        """
        if side not in ['long', 'short']:
            logging.info('{} - cancel_stop_order-side错误！'.format(self.symbol))
            return False

        orders_infos = self._get_other_orders()
        if type(orders_infos) is not list:
            return False

        cancel_order_ids = []
        for order_info in orders_infos:
            if order_info['type'] not in ['market', 'stop_market']:
                continue

            order_price = order_info['stopPrice']
            now_price = self.m.get_now_price()
            if side == 'long' and now_price < order_price:
                continue

            if side == 'short' and now_price > order_price:
                continue

            cancel_order_ids.append(order_info['id'])

        order_infos = self._cancel_order_for_ids(cancel_order_ids, params={
            'stop': True
        })

        if not all([order_infos, log]):
            return order_infos

        for order_info in order_infos:
            side_str = '清仓多头'
            if side == 'short':
                side_str = '清仓空头'
            logging.info("{} - 取消止损 - 成功取消${}的{}挂单".format(self.symbol, order_info['stopPrice'], side_str))

        return order_infos

    # 获取挂单仓位信息相关的内容
    def get_open_order_amount(self, side, price=None, log=False):
        """
        获取指定价格或者指定方向所有的挂单size
        :param side:
        :param price:
        :param log:
        :return:
        """
        if price:
            price = self.m.get_can_order_price(price)

        order_infos = self._get_open_orders(side, price)

        all_amount = 0
        for order_info in order_infos:
            amount = order_info['amount']
            # if log:
            #     side_str = "做多" if side == 'long' else '做空'
            #     logging.info("{} - 在${}已挂单{}了{}".format(self.symbol, order_info['price'], side_str, amount))
            all_amount += amount

        return all_amount * self.m.amount_size

    # 获取挂单数量
    def get_open_order_nums(self, side):
        """
        获取开仓订单数量
        :param side:
        :return:
        """
        if not self.is_future:
            side = 'long'
        orders = self._get_open_orders(side)
        if not orders:
            return 0
        return len(orders)

    def get_close_order_nums(self, side):
        """
        获取开仓订单数量
        :param side:
        :return:
        """
        if not self.is_future:
            side = 'long'
        orders = self._get_close_orders(side)
        return len(orders)

    def get_close_order_amount(self, side, price=None, log=False):
        """
        获取指定价格或者指定方向所有的挂单size
        :param side:
        :param price:
        :param log:
        :return:
        """
        if price:
            price = self.m.get_can_order_price(price)

        order_infos = self._get_close_orders(side, price)

        all_amount = 0
        for order_info in order_infos:
            amount = order_info['amount']
            # if log:
            #     side_str = "平空" if side == 'long' else '平多'
            # logging.info("{} - 在${}已挂单{}{}".format(self.symbol, order_info['price'], side_str, amount))
            all_amount += amount

        return all_amount * self.m.amount_size

    def get_stop_win_price(self, side, log=False):
        """
        获取止盈价格
        :param side:
        :param log:
        :return:
        """
        if side not in ['long', 'short']:
            logging.info('{} - get_stop_win_price-side错误！'.format(self.symbol))
            return False

        orders_infos = self._get_other_orders()
        if type(orders_infos) is not list:
            return False

        for order_info in orders_infos:
            if order_info['type'] not in ['market', 'take_profit_market']:
                continue

            order_price = order_info['stopPrice']
            now_price = self.m.get_now_price()
            if side == 'long' and now_price > order_price:
                continue

            if side == 'short' and now_price < order_price:
                continue

            # if log:
            #     side_str = '止盈多头'
            #     if side == 'short':
            #         side_str = '止盈空头'
            #     logging.info("{} - 在${}已挂单{}".format(self.symbol, order_info['price'], side_str))
            return order_price

        return False

    def get_stop_loss_price(self, side, log=False):
        """
        获取止损价格
        :param side:
        :param log:
        :return:
        """
        if side not in ['long', 'short']:
            logging.info('{} - get_stop_loss_price-side错误！'.format(self.symbol))
            return False

        orders_infos = self._get_other_orders()
        if type(orders_infos) is not list:
            return False

        for order_info in orders_infos:
            if order_info['type'] not in ['market', 'stop_market']:
                continue

            order_price = order_info['stopPrice']
            now_price = self.m.get_now_price()
            if side == 'long' and now_price < order_price:
                continue

            if side == 'short' and now_price > order_price:
                continue

            # if log:
            #     side_str = '止损多头'
            #     if side == 'short':
            #         side_str = '止损空头'
            #     logging.info("{} - 在${}已挂单{}".format(self.symbol, order_info['price'], side_str))

            return order_price

        return False

    # 获取最后一次交易收益信息
    def get_last_close_order_info(self):
        """
        获取最后一次交易收益信息
        """
        info = {
            "pnl": 0,
            "pnl_pnl": 0,
            "pnl_fee": 0,
        }
        history_list = self.exchange.fetchPositionsHistory([self.symbol])
        order_info = history_list[0]
        if order_info:
            info['pnl'] = order_info['info']['pnl']
            info['pnl_pnl'] = order_info['info']['pnl_pnl']
            info['pnl_fee'] = order_info['info']['pnl_fee']

        return info

    # 根据订单id进行一些订单内容的获取
    # def _get_order_id_info(self, order_id):
    #     """
    #     根据oder_id获取去具体的订单数据
    #     :param order_id:
    #     :return:
    #     """
    #     if self.exchange.id == 'binance':
    #         return self._get_orders()
    #     return self.handle('fetch_closed_orders', symbol=self.symbol, params={
    #         'stop': True,
    #         'status': 'open'
    #     })

    def test(self):
        logging.info(123)
        logging.info(self.exchange)
