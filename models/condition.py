from odoo import models, fields, exceptions, api
import talib
import talib.abstract as ta
import pandas as pd


class Condition(models.Model):
    _name = "fo.trading.condition"
    _description = "交易条件库"

    name = fields.Char("条件名称", required=True)
    args = fields.Char("条件参数", default="15m|2|args|1",
                       help="时间维度|返回值序列(1为前一根k线，0为当前K线)|talib计算df的参数，不填会用abstract计算|数值动态参数|结果倍数")
    load_mode = fields.Selection([('1', '指定函数'), ('2', 'TALIB')], required=True,
                                 default='2', string="加载方式",
                                 help='1-指定函数、2-talib的abstract、3-talib的函数需要传入指定参数')
    load_func = fields.Char("加载函数",
                            required=True, help="函数名称|返回取值")
    # timeframe = fields.Selection([('1m', '1分钟'), ('5m', '5分钟'), ('15m', '15分钟'),
    #                               ('30m', '30分钟'), ('1h', '1小时'), ('4h', '4小时'),
    #                               ('1d', '天线'), ('1w', '周线')], default='4h', string='时间周期')
    # res_series_name = fields.Char("ta-lib返回值", help="ta-lib获取series列的名字")
    # res_series_num = fields.Integer("返回值序列", default=2, help="从后向前取值，1为当前值，2为前根K线的值")
    is_enable = fields.Boolean("启用", default=False)
    remark = fields.Char("帮助文档")

    # @api.onchange('load_mode')
    # def _onchange_load_mode(self):
    #     if self.load_mode == '1':
    #         self.args = "15m|1|参数|1"
    #     elif self.load_mode == '2':
    #         self.args = "15m|1|df参数|参数|1"

    def enable(self):
        """
        启用
        :return:
        """
        # 1. 获取交易所
        exchange = self.env['fo.trading.exchange'].get_default_exchange()
        if not exchange:
            raise exceptions.ValidationError("请先创建默认交易所")

        # 2. 获取测试df数据
        symbol_name = "BTC/USDT:USDT"
        kd = exchange.kdata(symbol_name)
        # kd.update_kdata(self.timeframe, 200)
        # df = kd.df_4h
        value = self.get_value(kd, self.args)
        if not value:
            raise exceptions.ValidationError("未能成功计算条件结果！")
        self.is_enable = True

    @staticmethod
    def get_df(kd, timeframe, df_len=400):
        """
        获取对应timeframe的df
        :return:
        """
        df = getattr(kd, "df_{}".format(timeframe))
        if len(df) < df_len:
            kd.update_kdata(timeframe, df_len)
            df = getattr(kd, "df_{}".format(timeframe))
        return df

    def get_value(self, kd, args):
        """
        根据条件获取值
        需要获取到两个值，一个是当前值，一个是前一根K线计算出来的结果值
        :param args:
        :param kd:
        :return:
        """
        # 处理两个args中间的序列号 变成(2,1)这种类型
        value = 0
        args_list = args.split("|")
        ref = int(args_list[1])
        args2_list = args_list.copy()
        args_list[1] = str(ref + 1)
        args1_list = args_list
        args1 = "|".join(args1_list)
        args2 = "|".join(args2_list)
        if self.load_mode == '1':
            value = (self.get_func_value(kd, args1), self.get_func_value(kd, args2))
        elif self.load_mode == '2':
            value = (self.get_talib_value(kd, args1), self.get_talib_value(kd, args2))
        print("{} - {}:{} - 返回值：{}".format(kd.symbol, self.name, args, value))
        return value

    def _parse_args(self, args):
        """
        解析args
        1. 解析条件参数
            0: timeframe - 时间框架
            1: ref - 返回序列(1: 当前K线, 2: 前一根K线)
            2: func_args - 动态参数(直接传入到函数的args中)
            3: rate - 返回值倍数 float类型
        2. 解析加载函数
            0: func_name - 加载函数名
            1: func_res_name - 返回值名称(字典和dataframe数据取值的时候会用到)
        :param args: 15m|2|args|1
        :return:
        """
        # 1. 解析条件参数
        try:
            args_list = args.split('|')
            timeframe = args_list[0]  # 时间框架
            ref = int(args_list[1])  # 返回序列
            df_args = []
            func_args = []
            if args_list[2]:
                for arg in args_list[2].split(','):
                    if arg in ['open', 'high', 'low', 'close', 'volume']:
                        df_args.append(arg)
                        continue
                    func_args.append(arg)
            rate = float(args_list[3])
        except Exception as e:
            raise exceptions.ValidationError("{}-解析条件参数，参数是：{}".format(self.name, args))

        # 2. 解析加载函数
        try:
            func_list = self.load_func.split('|')
            func_name = func_list[0]
            func_res_name = False
            if len(func_list) > 1:
                func_res_name = func_list[1]
        except Exception as e:
            raise exceptions.ValidationError("{}-解析加载函数，参数是：{}".format(self.name, self.load_func))
        return {
            "timeframe": timeframe,
            "ref": ref,
            "df_args": df_args,
            "func_args": func_args,
            "rate": rate,
            "func_name": func_name,
            "func_res_name": func_res_name
        }

    def get_talib_value(self, kd, args):
        """
        获取TA的返回值
        1. 解析获取参数
        2. 加载df数据
        3. 动态加载方法， 加载参数
        4. 加载动态参数
        5. 计算值并且返回
        :param args:
        :param kd:
        :return:
        """
        # 1. 解析获取参数
        kwargs = self._parse_args(args)

        # 2. 加载df数据
        df = self.get_df(kd, kwargs["timeframe"], int(kwargs['func_args'][-1])+100)

        # 3. 动态调用加载方法, 加载参数
        indicator_args = []
        if kwargs["df_args"]:
            indicator_obj = getattr(talib, kwargs["func_name"])
            # 自定义talib需要加载talib对应的df-series
            for arg in kwargs["df_args"]:
                indicator_args.append(df[arg])
        else:
            indicator_obj = getattr(ta, kwargs["func_name"])
            indicator_args.append(df)

        # 4. 加载动态参数, 将所有参数转换成int类型
        indicator_args += [int(i) for i in kwargs["func_args"]]

        # 5. 计算值并且返回
        # 5.1执行计算
        indicator_df = indicator_obj(*indicator_args)
        # 5.2计算返回值，先判断indicator_df是dataframe还是series
        if isinstance(indicator_df, pd.DataFrame):
            try:
                indicator_df = indicator_df[kwargs["func_res_name"]]
            except Exception as e:
                raise exceptions.ValidationError("ta返回了dataframe取值的时候出现的错误")

        # 5.3 返回值1为当前K线，返回值2为前一根K线
        return indicator_df.iloc[-kwargs["ref"]] * kwargs["rate"]

    # def get_ta_lib_value(self, kd, args):
    #     """
    #     获取TA-LIB的返回值
    #     load_args= EMA,CLOSE  # 后面的没有会直接使用ta来进行计算
    #     1. 先根据args计算出args和res_series_num
    #         1.1 先加载args计算出对应的参数，并进行校验
    #     2. 解析load_args，获取ta-lib的对应的方法名称
    #     3. 加载附加的指标
    #     :param args:
    #     :param kd:
    #     :return:
    #     """
    #     # 1.先根据args计算出args和res_series_num
    #     # 1.1 加载args
    #     try:
    #         args_list = args.split('|')
    #         timeframe = args_list[0]
    #         ref = int(args_list[1])
    #         df_args = args_list[2]
    #         func_args = args_list[3]
    #         rate = float(args_list[4])
    #     except Exception as e:
    #         raise exceptions.ValidationError("{}-计算出现了错误，参数是：{}".format(self.name, args))
    #
    #     # 1.2 获取加载函数名和返回值
    #     try:
    #         func_list = self.load_func.split('|')
    #         func_name = func_list[0]
    #         func_res_name = func_list[1]
    #     except Exception as e:
    #         raise exceptions.ValidationError("{}-计算函数出现了问题，参数是：{}".format(self.name, self.load_func))
    #
    #     # 1.3 加载df数据
    #     df = self.get_df(kd, timeframe)
    #
    #     # 2. 判断选择加载ta还是talib, 并加载基础参数
    #     indicator_args = []  # 指标参数
    #     if df_args:
    #         try:
    #             for arg in df_args.split(","):
    #                 indicator_args.append(df[arg])
    #         except Exception as e:
    #             raise exceptions.ValidationError("ta解析df参数的时候出现了错误")
    #         indicator_obj = getattr(talib, func_name)
    #     else:
    #         indicator_args.append(df)
    #         indicator_obj = getattr(ta, func_name)
    #
    #     # 3. 加载附加的指标
    #     try:
    #         if func_args:
    #             for arg in func_args.split(","):
    #                 if isinstance(arg, str):
    #                     indicator_args.append(int(arg))
    #                 else:
    #                     indicator_args.append(arg)
    #     except Exception as e:
    #         raise exceptions.ValidationError("talib在解析传参的时候转int出现了错误")
    #
    #     # 执行计算
    #     indicator_df = indicator_obj(*indicator_args)
    #     # 计算返回值，先判断indicator_df是dataframe还是series
    #     if isinstance(indicator_df, pd.DataFrame):
    #         try:
    #             indicator_df = indicator_df[func_res_name]
    #         except Exception as e:
    #             raise exceptions.ValidationError("ta返回了dataframe取值的时候出现的错误")
    #
    #     # 默认返回前一天的数据就是-2，今天的数据就是-1
    #     return indicator_df.iloc[-ref - 1] * rate

    def get_func_value(self, kd, args):
        """
        直接将args传入函数，执行并返回结果
        :param args:
        :param kd:
        :return:
        """
        kwargs = self._parse_args(args)
        res = getattr(self, kwargs['func_name'])(kd, kwargs)

        if not res:
            raise exceptions.ValidationError("{}-自定义计算出错了：{}".format(self.name, args))

        return float(res) * kwargs['rate']


class ConditionFunc(models.Model):
    _inherit = 'fo.trading.condition'
    _description = '条件函数扩充'

    @staticmethod
    def get_target_price(*args):
        """
        获取目标价格
        :param args: 0:kd, 1:kwargs
        :return:
        """
        kwargs = args[1]
        return float(kwargs['func_args'][0])

    @staticmethod
    def get_now_price(*args):
        """
        获取当前价格
        :param args: 0:kd, 1:kwargs
        :return:
        """
        kd = args[0]
        return kd.m.get_now_price()

    def get_max_price(self, *args):
        """
        获取最大值
        :param args: 0:kd, 1:kwargs
        :return:
        """
        kd = args[0]
        kwargs = args[1]
        ref = kwargs["ref"] - 1
        max_ref = int(kwargs['func_args'][0])
        self.get_df(kd, kwargs["timeframe"], max_ref+10)
        return kd.get_kdata_max_price(kwargs["timeframe"], ref=ref, max_ref=max_ref)

    def get_min_price(self, *args):
        """
        获取最小值
        :param args: 0:kd, 1:kwargs
        :return:
        """
        kd = args[0]
        kwargs = args[1]
        ref = kwargs["ref"] - 1
        max_ref = int(kwargs['func_args'][0])
        self.get_df(kd, kwargs["timeframe"], max_ref+10)
        return kd.get_kdata_min_price(kwargs["timeframe"], ref=ref, max_ref=max_ref)

    def get_k_value(self, *args):
        """
        获取K线数据
         - open 开盘价
         - close 收盘价
         - high 最高价
         - low 最低价
         - volume 成交量
        :param args:  0:kd, 1:kwargs
        :return:
        """
        kd = args[0]
        kwargs = args[1]
        ref = kwargs["ref"] - 1
        # get_name = kwargs['func_args'][0]
        get_name = kwargs['df_args'][0]
        self.get_df(kd, kwargs["timeframe"], 20)
        k_value = getattr(kd, "get_{}".format(get_name))(kwargs["timeframe"], ref=ref)
        if not k_value:
            raise exceptions.ValidationError("{}-获取K线数据失败".format(self.name))
        return k_value
