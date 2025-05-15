from odoo import models, api, fields
from datetime import timedelta


class Monitor(models.Model):
    _name = "fo.trading.monitor"
    _description = '监控系统'

    name = fields.Char("监控名称")
    state = fields.Selection([('1', '未启动'), ('2', '监控中')], default='1', string="状态")

    timeframe = fields.Selection([('1m', '1分钟'), ('5m', '5分钟'), ('15m', '15分钟'),
                                  ('30m', '30分钟'), ('1h', '1小时'), ('4h', '4小时'),
                                  ('1d', '天线'), ('1w', '周线')], string='时间周期', default='15m', required=True)
    last_execute_time = fields.Datetime("上次执行时间", default=fields.Datetime.now)
    next_execute_time = fields.Datetime("下次执行时间", default=fields.Datetime.now)
    notification_num = fields.Integer("通知次数", default=1)
    already_notification_num = fields.Integer("已通知次数", default=0)

    # 外键字段
    monitor_sub_ids = fields.One2many("fo.trading.monitor.sub",
                                      "monitor_id", string="条件列表")
    symbol_ids = fields.Many2many("fo.trading.symbol", string="监控币", required=True)

    @staticmethod
    def _get_timeframe_value(timeframe):
        """
        通过timeframe的str格式来计算出int数值
        :param timeframe:
        :return:
        """
        return {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}[timeframe]

    # @api.onchange('monitor_sub_ids')
    # def _onchange_monitor(self):
    #     """
    #     出现变化的时候自动计算timeframe
    #     :return:
    #     """
    #     i = 0
    #     min_i = 0
    #     timeframe = None
    #     min_v = 10000
    #     if not self.timeframe and self.monitor_sub_ids:
    #         # 获取最小的时间框架的min_v和min_i的值
    #         for instance in self.monitor_sub_ids:
    #             # 先获取timeframe的最小值
    #             timeframe1 = instance.a_args.split("|")[0]
    #             timeframe2 = instance.b_args.split("|")[0]
    #             v1 = self._get_timeframe_value(timeframe1)
    #             v2 = self._get_timeframe_value(timeframe2)
    #             v = min(v1, v2)
    #             if v < min_v:
    #                 min_v = v
    #                 min_i = i
    #             i += 1
    #         # 设置timeframe
    #         self.timeframe = self.monitor_sub_ids[min_i].timeframe

    def start_monitor(self):
        """
        开启监控
        :return:
        """
        self.state = '2'
        self.last_execute_time = fields.Datetime.now()
        self.next_execute_time = fields.Datetime.now()

    def stop_monitor(self):
        """
        停止监控
        :return:
        """
        self.state = '1'
        self.already_notification_num = 0

    def test(self):
        """
        测试监控
        :return:
        """
        exchange = self.env['fo.trading.exchange'].get_default_exchange()
        kd = exchange.kdata(self.symbol_ids[0].name)
        res = self.start(kd)
        print(res)

    def start(self, kd):
        """
        判断所有条件是否满足
        循环判断每一个条件列表，必须全部通过才算条件成功
        1. 初始化条件中的a,b,timeframe的参数
        2. 判断是否已经存在指定条件的计算出来的值
        3. 计算a条件和b条件的值
        4. 判断a条件和b条件是否满足state的要求，不满足直接返回False
        :return:
        """
        # 1. 获取交易所对象
        value_data = {}
        # 2. 循环每个条件进行判断
        res = False
        for monitor_sub in self.monitor_sub_ids:
            #  1. 初始化条件中的a,b,timeframe的参数
            a = monitor_sub.a
            b = monitor_sub.b
            # timeframe = monitor_sub.timeframe
            # 2. 判断是否已经存在指定条件的计算出来的值
            # 2.1 计算a值
            a_value_name = "{}_{}".format(a.display_name, monitor_sub.a_args)
            if not value_data.get(a_value_name):
                # 3. 计算a条件和b条件的值
                value_data[a_value_name] = a.get_value(kd, monitor_sub.a_args)
            # 2.2 计算b值
            b_value_name = "{}_{}".format(b.display_name, monitor_sub.b_args)
            if not value_data.get(b_value_name):
                # 3. 计算a条件和b条件的值
                value_data[b_value_name] = b.get_value(kd, monitor_sub.b_args)

            # 4. 判断a条件和b条件是否满足state的要求，不满足直接返回False
            a1 = value_data[a_value_name][0]  # a值取值的前一根值
            b1 = value_data[b_value_name][0]  # b值取值的前一根值
            a2 = value_data[a_value_name][1]  # a取的值
            b2 = value_data[b_value_name][1]  # b取的值
            if monitor_sub.state == '1':
                # 大于
                res = a2 > b2
            elif monitor_sub.state == '2':
                # 小于
                res = a2 < b2
            elif monitor_sub.state == '3':
                # 上穿
                tj1 = a2 > b2  # a2大于b2, 今天的a值要比b值大
                tj2 = a1 < b1  # a1小于b1, 昨天的a值要比b值小
                res = tj1 and tj2  # 两个都满足则出现上穿的情况
            elif monitor_sub.state == '4':
                # 下穿
                tj1 = a2 < b2  # a2小于b2, 今天的a值要比b值小
                tj2 = a1 > b1  # a1大于b1, 昨天的a值要比b值大
                res = tj1 and tj2  # 两个都满足则出现下穿的情况
            elif monitor_sub.state == '5':
                # 触碰, 上穿或者下穿都行
                tj1 = a2 > b2 and a1 < b1
                tj2 = a2 < b2 and a1 > b1
                res = tj1 or tj2

            if not res:
                return False
            return res

    def _cron(self):
        """
        定时任务, 自动进行监控
        :return:
        """
        exchange = self.env['fo.trading.exchange'].get_default_exchange()
        instances = self.search([('state', '=', '2')])
        c = exchange.compute("BTC/USDT:USDT")
        kd_dict = {}
        # 循环每个监控中的策略
        for instance in instances:
            # 判断一下当前的时间，如果未到执行时间则跳过
            if fields.Datetime.now() < instance.next_execute_time:
                continue
            # 设置一下上次执行时间和下次执行时间
            next_time = c.get_next_run_time(fields.Datetime.now(), instance.timeframe)
            instance.next_execute_time = next_time
            instance.last_execute_time = fields.Datetime.now()
            symbol_instances = instance.symbol_ids
            notification_symbol_list = []
            # 循环每个策略中的币种， kd的作用就是防止重复获取服务器的KD数据
            for symbol_instance in symbol_instances:
                symbol = symbol_instance.name
                symbol_id = symbol_instance.id
                kd = kd_dict.get(symbol)
                if not kd:
                    kd = exchange.kdata(symbol)
                    kd_dict[symbol] = kd
                # res为指定种类指定币种的监控结果
                res = instance.start(kd)
                if res:
                    notification_symbol_list.append(symbol_id)
            # 创建通知
            if notification_symbol_list:
                self.env['fo.trading.notification'].create({
                    'monitor_id': instance.id,
                    'symbol_ids': [(6, 0, notification_symbol_list)]
                })
                # 通知之后处理一下
                instance.already_notification_num += 1
                if 0 < instance.notification_num <= instance.already_notification_num:
                    instance.stop_monitor()


class MonitorSub(models.Model):
    _name = "fo.trading.monitor.sub"
    _description = '监控系统条件'

    state = fields.Selection([('1', '大于'), ('2', '小于'), ('3', "上穿"), ('4', "下穿"), ("5", "触碰")],
                             default='1', string="满足")
    a_args = fields.Char("条件A参数", required=True)
    b_args = fields.Char("条件B参数", required=True)
    # timeframe = fields.Selection([('1m', '1分钟'), ('5m', '5分钟'), ('15m', '15分钟'),
    #                               ('30m', '30分钟'), ('1h', '1小时'), ('4h', '4小时'),
    #                               ('1d', '天线'), ('1w', '周线')], default='4h', string='时间周期')

    # 外键字段
    monitor_id = fields.Many2one("fo.trading.monitor", string="监控名")
    a = fields.Many2one('fo.trading.condition', string="条件A", required=True,
                        domain=[('is_enable', '=', True)])
    b = fields.Many2one('fo.trading.condition', string="条件B", required=True,
                        domain=[('is_enable', '=', True)])

    @api.onchange("a", 'b')
    def _onchange_a_b(self):
        """
        A参数修改
        :return:
        """
        if self.a:
            # self.a_args = "{}|1".format(self.a.args if self.a.args else "")
            self.a_args = self.a.args
        if self.b:
            # self.b_args = "{}|1".format(self.b.args if self.b.args else "")
            self.b_args = self.b.args

    # def _judge(self, ):
