from odoo import models, fields, api, exceptions


class Positions(models.Model):
    _name = "fo.trading.positions"
    _description = "仓位管理"

    name = fields.Char("仓位ID")

    # order_uid = fields.Char("订单ID")

    def _default_timeframe(self):
        """
        获取偏好周期
        :return:
        """
        instance = self.env['fo.trading.exchange'].search([('is_default', '=', True)], limit=1)
        if not instance:
            return "5m"

        return instance.timeframe

    timeframe = fields.Selection([('1m', '1分钟'), ('5m', '5分钟'), ('15m', '15分钟'),
                                  ('30m', '30分钟'), ('1h', '1小时'), ('4h', '4小时'),
                                  ('1d', '天线'), ('1w', '周线')], string='时间周期', default=_default_timeframe,
                                 required=True)
    state = fields.Selection([('-1', "编辑中"), ('0', '待买入'), ('1', '持仓中'), ("2", "已结束"), ('3', "未成交")],
                             default='1',
                             string="状态")
    side = fields.Selection([('long', '多头'), ('short', '空头')], string="方向")

    open_time = fields.Char("开仓时间")
    entry_price = fields.Float("入场价格", digits=(16, 9))
    stop_loss_price = fields.Float("止损价格", digits=(16, 9))
    stop_win_price = fields.Float("止盈价格", digits=(16, 9))
    last_stop_loss_price = fields.Float("上次止损价格", digits=(16, 9))
    last_stop_win_price = fields.Float("上次止盈价格", digits=(16, 9))
    max_win = fields.Float("最大收益", default=0)
    max_loss = fields.Float("最大盈亏")
    now_loss = fields.Float("止损盈亏")
    value = fields.Float("仓位价值")
    amount = fields.Float("仓位数量")
    pnl = fields.Float("收益额", digits=(16, 3))
    pnl_fee = fields.Float("手续费", digits=(16, 3))

    max_win_rate = fields.Float("最大盈亏比", digits=(16, 3), default=0.0, store=True)

    is_stop_win_1 = fields.Boolean("已经第一次止盈", default=False)
    is_add_position_1 = fields.Boolean("已经第一次加仓", default=False)

    pnl_rate = fields.Float("盈亏比", digits=(16, 3), default=0.0, compute="_compute_pnl_rate", store=True)
    symbol_id = fields.Many2one("fo.trading.symbol", "币种")
    trading_order_ids = fields.One2many("fo.trading.trading.order",
                                        "position_id", "交易记录")

    last_execute_time = fields.Datetime("上次执行时间", default=fields.Datetime.now)
    next_execute_time = fields.Datetime("下次执行时间", default=fields.Datetime.now)

    # @api.depends('max_win', 'max_loss')
    # def _compute_max_win_rate(self):
    #     """
    #     计算最大盈亏比
    #     :return:
    #     """
    #     for instance in self:
    #         if instance.max_win and instance.max_loss:
    #             instance.max_win_rate = instance.max_win / abs(instance.max_loss)
    #         else:
    #             instance.max_win_rate = 0

    @api.depends('write_date')
    def _compute_pnl_rate(self):
        """
        计算盈亏比
        :return:
        """
        for instance in self.filtered_domain([('state', '=', '1')]):
            if instance.pnl and instance.max_loss:
                instance.pnl_rate = instance.pnl / abs(instance.max_loss)
                if instance.pnl_rate > instance.max_win_rate:
                    instance.max_win_rate = instance.pnl_rate
            else:
                instance.pnl_rate = 0

    # 外键字段
    def compute_best_atr(self):
        """
        计算最佳的收益
        :return:
        """
        profit = 0
        profit_1 = 0
        profit_2 = 0
        profit_3 = 0
        profit_4 = 0
        profit_5 = 0
        profit_6 = 0
        profit_7 = 0
        profit_8 = 0
        profit_9 = 0
        profit_10 = 0
        for instance in self.search([]):
            profit += instance.pnl_rate
            if instance.max_win_rate >= 1:
                profit_1 += 1
            else:
                profit_1 += instance.pnl_rate

            if instance.max_win_rate > 2:
                profit_2 += 2
            else:
                profit_2 += instance.pnl_rate

            if instance.max_win_rate > 3:
                profit_3 += 3
            else:
                profit_3 += instance.pnl_rate

            if instance.max_win_rate > 4:
                profit_4 += 4
            else:
                profit_4 += instance.pnl_rate

            if instance.max_win_rate > 5:
                profit_5 += 5
            else:
                profit_5 += instance.pnl_rate

            if instance.max_win_rate > 6:
                profit_6 += 6
            else:
                profit_6 += instance.pnl_rate

            if instance.max_win_rate > 7:
                profit_7 += 7
            else:
                profit_7 += instance.pnl_rate

            if instance.max_win_rate > 8:
                profit_8 += 8
            else:
                profit_8 += instance.pnl_rate

            if instance.max_win_rate > 9:
                profit_9 += 9
            else:
                profit_9 += instance.pnl_rate

            if instance.max_win_rate > 10:
                profit_10 += 10
            else:
                profit_10 += instance.pnl_rate

        print("总收益：{}".format(profit))
        print("1倍ATR收益：{}".format(profit_1))
        print("2倍ATR收益：{}".format(profit_2))
        print("3倍ATR收益：{}".format(profit_3))
        print("4倍ATR收益：{}".format(profit_4))
        print("5倍ATR收益：{}".format(profit_5))
        print("6倍ATR收益：{}".format(profit_6))
        print("7倍ATR收益：{}".format(profit_7))
        print("8倍ATR收益：{}".format(profit_8))
        print("9倍ATR收益：{}".format(profit_9))
        print("10倍ATR收益：{}".format(profit_10))

    def test(self):
        print(1111)
        exchange = self.env['fo.trading.exchange'].get_default_exchange()
        if not exchange:
            raise exceptions.ValidationError("请先创建默认交易所")

        # 1.2. 获取所有当前仓位信息
        positions_list = exchange.exchange.fetch_positions(params={"holding": True})

        print(123)
        # self._update_positions()

    # def _update_positions(self):
    #     """
    #     更新仓位信息
    #     1. 获取API最新的仓位信息
    #     2. 循环API获得的仓位信息
    #     3. 遍历更新仓位管理中的仓位信息
    #         存在则更新
    #         不存在则创建
    #     4. 将不存在的仓位进行结束处理
    #     :return:
    #     """
    #     # 1. 获取API最新的仓位信息
    #     # 1.1 获取交易所
    #     exchange = self.env['fo.trading.exchange'].get_default_exchange()
    #     if not exchange:
    #         raise exceptions.ValidationError("请先创建默认交易所")
    #
    #     # 1.2. 获取所有当前仓位信息
    #     positions_list = exchange.exchange.fetch_positions(params={"holding": True})
    #     positions_instances = self.search([('state', '=', '1')])
    #     has_position_symbol_list = []
    #
    #     # 2. 循环API获得仓位信息
    #     for position in positions_list:
    #         # 3. 遍历更新仓位信息
    #         entry_price = float(position['entryPrice'])  # 入场价格
    #         pnl_fee = float(position['info']["pnl_fee"])  # 手续费
    #         now_pnl = float(position['unrealizedPnl'] + position['realizedPnl'])  # 当前盈亏 - 已实现和未实现盈亏之和
    #         amount = float(position['contracts']) * float(position['contractSize'])  # 持有数量
    #         value = float(position['notional'])  # 持有金额
    #         side = position['side']  # 方向
    #         open_time = position['timestamp']  # 开仓时间
    #         symbol_name = position['symbol']  # 币种名称
    #         has_position_symbol_list.append(symbol_name)
    #         update_data = {
    #             'open_time': open_time,
    #             "entry_price": entry_price,
    #             "value": value,
    #             "amount": amount,
    #             "side": side,
    #         }
    #
    #         # 3.1 获取symbol_id
    #         symbol_instance = self.env['fo.trading.symbol'].search([('name', '=', symbol_name)])
    #         if not symbol_instance:
    #             symbol_instance = self.env['fo.trading.symbol'].create({
    #                 'name': symbol_name
    #             })
    #         symbol_id = symbol_instance.id
    #
    #         # 3.2 获取仓位对象
    #         position_instance = positions_instances.filtered_domain([('symbol_id', '=', symbol_id)])
    #         if not position_instance:
    #             # 3.3 不存在则创建对象
    #             update_data['symbol_id'] = symbol_id
    #             # update_data['name'] = "{}-{}".format(symbol_name, open_time)
    #             update_data['name'] = "{}-{}".format(symbol_name.split('/')[0], open_time)
    #             self.create(update_data)
    #             continue
    #
    #         # 3.3 更新对象
    #         position_instance.update(update_data)
    #
    #     # 4. 将不存在的仓位进行结束处理
    #     for instance in positions_instances:
    #         if instance.symbol_id.name not in has_position_symbol_list:
    #             instance.state = '2'
    #             if not instance.symbol_id:
    #                 continue
    #             # 计算收益
    #             u = exchange.user(instance.symbol_id.name)
    #             pnl_info = u.get_open_time_pnl_info(instance.open_time)
    #             instance.pnl = pnl_info['pnl']
    #             instance.pnl_fee = pnl_info['pnl_fee']

    def get_all_position_max_loss(self):
        """
        获取所有仓位一起的最大亏损金额
        :return:
        """
        all_max_loss = 0
        instances = self.search([('state', '=', '1')])
        for instance in instances:
            all_max_loss += instance.now_loss

        return all_max_loss

    def update_positions(self):
        """
        更新仓位信息, 暂时使用天空之城策略进行仓位自动化客观交易
        1. 获取交易所对象
        2. 获取API最新的仓位信息
        3. 循环处理每个系统获取的position
        4. 获取状态为0,1的instance_list, 如果不在处理列表中，就结束并计算pnl
        :return:
        """
        # 1. 获取交易所对象
        exchange = self.env['fo.trading.exchange'].get_default_exchange()
        if not exchange:
            raise exceptions.ValidationError("请先创建默认交易所")

        # 2. API获取最新的仓位信息
        positions_list = exchange.exchange.fetch_positions(params={"holding": True})

        # 3. 循环处理每个系统获取的position
        handle_position_id_list = []
        for position in positions_list:
            # 3.1 加载position的数据
            position_data = self.parse_position(position)

            # 检查一下是否在自动网格中已经有运行，如果有直接跳过
            grid_instance = self.env['fo.trading.grid.trading'].search([('state', '=', '2'),
                                                                        ('symbol_id', '=', position_data['symbol_id'])])
            if grid_instance:
                continue

            # 3.2 加载position_instance
            # 先加载待买入的position_instance
            position_instance = self.search([('symbol_id', '=', position_data['symbol_id']),
                                             ('side', '=', position_data['side']), ('state', '=', '0')])

            # 不存在则且状态是1的情况，直接获取state1的数据，这里可以使用开仓的timestamp来进行判断
            if not position_instance and position_data['open_time']:
                position_instance = self.search([('open_time', '=', position_data['open_time']),
                                                 ('side', '=', position_data['side']),
                                                 ('symbol_id', '=', position_data['symbol_id'])], limit=1)

            # 3.3 判断是否存在position_instance, 不存在创建，存在则更新
            if not position_instance:
                # 3.3.1 创建position_instance
                position_instance = self.create(position_data)
            else:
                # 3.3.2 更新position_instance
                position_instance.update(position_data)

            # 执行一下position自动创建order的事情auto_create_order_instance_for_order_list(self, exchange, symbol_name)
            position_instance.trading_order_ids.auto_create_order_instance_for_order_list(
                exchange, position_instance.symbol_id.name, position_instance)

            # 4. 执行策略
            position_instance.run_trading(exchange)
            # position_instance.sky_city_strategy(exchange)
            handle_position_id_list.append(position_instance.id)

        # 4. 获取状态为0,1的instance_list, 如果不在处理列表中，就结束并计算pnl
        position_instances = self.search([('state', 'in', ['0', '1'])])
        for instance in position_instances:
            if instance.id not in handle_position_id_list:
                u = exchange.user(instance.symbol_id.name)
                # o = exchange.order(instance.symbol_id.name)
                # 4.1 更新状态
                state = '2'
                if instance.state == '0':
                    # 如果是待成交检查一下是否有open的订单，有的话直接退出
                    is_open = False
                    for order_instance in instance.trading_order_ids:
                        order_instance.update_for_exchange(exchange)
                        if order_instance.state == 'open':
                            is_open = True
                            break
                    # 如果有开仓则去找下一个运行
                    if is_open:
                        continue
                    # 如果待成交结束那么状态就是未成交
                    state = '3'
                instance.state = state
                pnl_info = u.get_open_time_pnl_info(instance.open_time)
                instance.pnl = pnl_info['pnl']
                instance.pnl_fee = pnl_info['pnl_fee']
                # o.cancel_open_order(instance.side)
                # o.cancel_close_order(instance.side)
                continue

        # 5. 删除未成交的所有数据
        position_instances = self.search([('state', '=', '3')])
        for instance in position_instances:
            instance.unlink()

    def parse_position(self, position):
        """
        解析position的值
        "open_time": position['timestamp'],  # 开仓时间
        "entry_price": float(position['entryPrice']),  # 入场价格
        "pnl_fee": float(position['info']["pnl_fee"]),  # 手续费
        "pnl": float(position['unrealizedPnl'] + position['realizedPnl']),  # 当前盈亏 - 已实现和未实现盈亏之和
        "amount": float(position['contracts']) * float(position['contractSize']),  # 持有数量
        "value": float(position['notional']),  # 持有金额
        "side": side,  # 方向
        "symbol_name": symbol_name,  # 币种名称
        "symbol_id": symbol_id,  # 币种ID
        1. 先计算symbol_id
        2. 加载side方向
        3. 加载data的数据
        """
        # 1. 计算symbol_id
        symbol_name = position['symbol']  # 币种名称
        symbol_instance = self.env['fo.trading.symbol'].search([('name', '=', symbol_name)])
        if not symbol_instance:
            symbol_instance = self.env['fo.trading.symbol'].create({
                'name': symbol_name
            })
        symbol_id = symbol_instance.id

        # 2. 计算side方向
        side = position['info']['mode']  # 方向
        side = side.split('_')[1]

        amount = float(position['contracts'])
        if position['contractSize']:
            amount = amount * float(position['contractSize'])

        # 3. 加载data的数据
        data = {
            'name': "{}-{}".format(symbol_name.split('/')[0], position['timestamp']),
            'state': '1' if position['timestamp'] else '0',
            "open_time": position['timestamp'],  # 开仓时间
            "entry_price": float(position['entryPrice']),  # 入场价格
            "pnl_fee": float(position['info']["pnl_fee"]),  # 手续费
            "pnl": float(position['unrealizedPnl'] + position['realizedPnl']),  # 当前盈亏 - 已实现和未实现盈亏之和
            "amount": amount,  # 持有数量
            "value": float(position['notional']),  # 持有金额
            "side": side,  # 方向
            # "symbol_name": symbol_name,  # 币种名称
            "symbol_id": symbol_id,  # 币种ID
        }
        return data

    def run_trading(self, exchange):
        """
        运行交易
        1. 止损挂单
        2. 止盈挂单
        3. 循环更新订单流
        :param exchange:
        :return:
        """
        o = exchange.order(self.symbol_id.name)
        c = exchange.compute(self.symbol_id.name)
        # 先执行订单流交易
        # if self.trading_order_ids:
        #     self.run_trading_order(exchange)

        # 判断状态, 不是运行中不需要进行止损止盈的操作
        if self.state != '1':
            return

        # 止损挂单
        self.run_stop_loss_order(exchange)
        # return

        # 止盈挂单
        if not self.stop_win_price and self.last_stop_win_price:
            # 如果当前没有止盈价格，但是上次有止盈价格，取消所有止盈订单
            o.close_order(self.side)
        elif self.stop_win_price and self.last_stop_win_price != self.stop_win_price:
            # 如果当前有止盈价格，而且上次止盈价格和当前止盈价格不一样，更新止盈价格
            self.run_stop_win_order(exchange)

        # 进行止损止盈的赋值
        self.last_stop_loss_price = self.stop_loss_price
        self.last_stop_win_price = self.stop_win_price

        # 进行第一次加仓的操作
        if not self.is_add_position_1 and self.amount > 0:
            self.is_add_position_1 = True
            exchange_instance = self.env['fo.trading.exchange'].search([('is_default', '=', True)], limit=1)
            max_loss = exchange_instance.get_symbol_max_loss(symbol=self.symbol_id.name,
                                                             exchange=exchange)
            if not max_loss:
                return 0
            need_buy_amount = c.get_buy_amount_for_stop_price(self.side,
                                                              self.stop_loss_price,
                                                              max_loss,
                                                              c.m.get_now_price())
            # 没有需要加仓的单位
            need_buy_amount = need_buy_amount - self.amount
            if need_buy_amount <= 0:
                return

            # 执行加仓操作, 市价操作
            o.open_order(self.side, need_buy_amount)

        # 进行动态止盈，目前4倍ATR收益最高
        if self.is_stop_win_1:
            # 如果已经执行过了就不需要重复执行了
            return

        # 当最大ATR大于4的时候继续执行
        if self.max_win_rate < 4:
            return

        # 当前ATR小于最大ATR-1的时候，减仓一半先
        if self.pnl_rate < self.max_win_rate - 1:
            # 进行减仓
            o.close_order(self.side, self.amount / 2)
            self.is_stop_win_1 = True

    def run_stop_loss_order(self, exchange):
        """
        运行止损交易

        :param exchange:
        :return:
        """
        # 获取交易所对象
        u = exchange.user(self.symbol_id.name)
        o = exchange.order(self.symbol_id.name)
        c = exchange.compute(self.symbol_id.name)
        kd = exchange.kdata(self.symbol_id.name)

        stop_loss_price = c.compute_stop_loss_price(self.side, kd, timeframe=self.timeframe)
        # 2.4 获取当前市场的止损点位,根据当前市场的止损点位，重新进行计算止损价格
        now_stop_loss_price = o.get_stop_loss_price(self.side)
        if now_stop_loss_price and self.side == 'long':
            stop_loss_price = max(stop_loss_price, now_stop_loss_price)
        elif now_stop_loss_price and self.side == 'short':
            stop_loss_price = min(stop_loss_price, now_stop_loss_price)
        # 2.5 根据系统设置的止损点位，重新设置止损点位
        if self.stop_loss_price and self.side == 'long':
            stop_loss_price = max(stop_loss_price, self.stop_loss_price)
        elif self.stop_loss_price and self.side == 'short':
            stop_loss_price = min(stop_loss_price, self.stop_loss_price)

        # 3. 设置新的止损
        if now_stop_loss_price != stop_loss_price:
            o.stop_order_for_price(self.side, stop_loss_price)

        # 3.1 计算now_loss， now_loss是正数， max_loss会取负数
        if self.stop_loss_price != stop_loss_price or now_stop_loss_price != stop_loss_price:
            now_loss = -u.get_appoint_stop_loss_max_loss(self.side, stop_loss_price)
            self.now_loss = now_loss
            if now_loss < self.max_loss:
                self.max_loss = now_loss
            self.stop_loss_price = stop_loss_price

        # 4. 计算最大收益
        if self.pnl > self.max_win:
            self.max_win = self.pnl

    def run_stop_win_order(self, exchange):
        """
        运行止盈交易
        :param exchange:
        :return:
        """
        pass

    # def update_position_for_now_positions_list(self, exchange, positions_list):
    #     """
    #     根据positions_list更新仓位信息，循环处理每一个position
    #     1. 加载position数据
    #     2. 判断当前持仓是否存在当前symbol-side
    #         - 如果存在则更新
    #         - 如果不存在则创建
    #     :param exchange: 交易所对象
    #     :param positions_list: 通过API获得的仓位信息
    #     :return: not_ok_list 没有仓位的币种列表
    #     """
    #     not_ok_list = []
    #     for position in positions_list:
    #         # 1. 加载position数据
    #         open_time = position['timestamp']  # 开仓时间
    #         if not open_time:
    #             continue
    #         # order_uid = position['id']  # 订单ID
    #         entry_price = float(position['entryPrice'])  # 入场价格
    #         pnl_fee = float(position['info']["pnl_fee"])  # 手续费
    #         pnl = float(position['unrealizedPnl'] + position['realizedPnl'])  # 当前盈亏 - 已实现和未实现盈亏之和
    #         amount = float(position['contracts']) * float(position['contractSize'])  # 持有数量
    #         value = float(position['notional'])  # 持有金额
    #         side = position['side']  # 方向
    #         symbol_name = position['symbol']  # 币种名称
    #         # state = '1'
    #         # if not open_time:
    #         #     state = '0'
    #         #     not_ok_list.append("{}-{}".format(symbol_name, side))
    #
    #         # 2. 判断当前持仓是否存在当前symbol-side
    #         # 2.1 获取symbol_id
    #         symbol_instance = self.env['fo.trading.symbol'].search([('name', '=', symbol_name)])
    #         if not symbol_instance:
    #             symbol_instance = self.env['fo.trading.symbol'].create({
    #                 'name': symbol_name
    #             })
    #         symbol_id = symbol_instance.id
    #         # 2.2 获取仓位对象
    #         # instance = self.search([('symbol_id', '=', symbol_id), ('side', '=', side), ('state', 'in', ['0', '1'])])
    #         # instance = self.search([('symbol_id', '=', symbol_id), ('side', '=', side), ('state', '=', '1')])
    #         instance = self.search([
    #             ('open_time', '=', open_time), ('side', '=', side), ('symbol_id', '=', symbol_id)], limit=1)
    #
    #         # 2.3 如果存在则更新
    #         data = {
    #             'name': "{}-{}".format(symbol_name.split('/')[0], open_time),
    #             # 'order_uid': order_uid,
    #             # 'state': state,
    #             "entry_price": entry_price,
    #             "pnl_fee": pnl_fee,
    #             "pnl": pnl,
    #             "amount": amount,
    #             "value": value,
    #             "side": side,
    #             'open_time': open_time,
    #             'symbol_id': symbol_id,
    #         }
    #         if instance:
    #             instance.update(data)
    #             continue
    #         # 2.4 如果不存在则创建
    #         self.create(data)
    #
    #     return not_ok_list
    #
