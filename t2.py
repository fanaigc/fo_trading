# def calculate_grid_positions(max_loss, upper_limit, lower_limit, grid_count):
#     """
#     计算网格交易策略中每个网格位置应该买入的数量
#
#     参数:
#     max_loss (float): 最大允许亏损金额
#     upper_limit (float): 网格价格上限，高于此价格仓位为0
#     lower_limit (float): 网格价格下限
#     grid_count (int): 网格数量
#
#     返回:
#     dict: 包含网格价格和对应仓位数量的字典
#     float: 每个网格的买入量
#     float: 每次网格套利的收益
#     """
#     # 检查输入参数
#     if lower_limit >= upper_limit:
#         raise ValueError("下限价格必须小于上限价格")
#     if grid_count <= 0:
#         raise ValueError("网格数量必须为正整数")
#     if max_loss <= 0:
#         raise ValueError("最大亏损金额必须为正数")
#
#     # 计算每个网格的价格区间
#     grid_interval = (upper_limit - lower_limit) / grid_count
#
#     # 计算网格价格列表
#     grid_prices = [upper_limit - i * grid_interval for i in range(grid_count + 1)]
#
#     # 计算每个网格位置的仓位份数
#     positions = {i: i for i in range(grid_count + 1)}
#
#     # 计算最坏情况下的亏损（价格从下限跌到0）
#     # 在这种情况下，所有网格都会被触发，总仓位为 n*(n+1)/2
#     total_positions = grid_count * (grid_count + 1) / 2
#
#     # 计算每份仓位应该买入的数量
#     # 最坏情况亏损 = 总购买金额（即所有网格的买入量 * 对应价格之和）
#     # 我们需要保证这个亏损不超过max_loss
#
#     # 计算所有网格买入的总金额
#     total_investment = 0
#     for i in range(1, grid_count + 1):
#         grid_price = grid_prices[i]
#         total_investment += i * grid_price
#
#     # 计算每份仓位的单位金额（即每个网格买入多少钱）
#     unit_investment = max_loss / total_investment
#
#     # 计算每个网格的买入量（金额/价格）
#     position_sizes = {}
#     for i in range(grid_count + 1):
#         grid_price = grid_prices[i]
#         position_count = positions[i]
#
#         # 对于价格为0的极端情况进行处理
#         if grid_price > 0:
#             # 买入数量 = 仓位份数 * 单位金额 / 价格
#             position_size = position_count * unit_investment / grid_price
#         else:
#             position_size = 0
#
#         position_sizes[grid_price] = position_size
#
#     # 计算每次网格套利的收益
#     # 每次网格套利的收益 = 单位金额 * 网格价格区间 / 价格
#     profit_per_grid = unit_investment * grid_interval / upper_limit
#
#     # 构建返回结果
#     grid_positions = {}
#
#     for i, price in enumerate(grid_prices):
#         grid_positions[price] = positions[i]
#
#     return grid_positions, unit_investment, profit_per_grid
#
#
# # 使用示例
# if __name__ == "__main__":
#     # 参数设置
#     max_loss = 100  # 最大亏损金额
#     upper_limit = 100  # 网格价格上限
#     lower_limit = 95  # 网格价格下限
#     grid_count = 6  # 网格数量
#
#     # 计算网格仓位
#     grid_positions, unit_investment, profit_per_grid = calculate_grid_positions(
#         max_loss, upper_limit, lower_limit, grid_count
#     )
#
#     # 输出结果
#     print(f"网格交易参数设置:")
#     print(f"最大亏损金额: {max_loss}")
#     print(f"网格价格上限: {upper_limit}")
#     print(f"网格价格下限: {lower_limit}")
#     print(f"网格数量: {grid_count}")
#     print("\n")
#
#     print(f"每单位仓位投资金额: {unit_investment:.4f}")
#     print(f"每次网格套利收益: {profit_per_grid:.4f}")
#     print("\n")
#
#     print("网格价格和对应仓位数量:")
#     for price, position in sorted(grid_positions.items(), reverse=True):
#         buy_amount = position * unit_investment / price if price > 0 else 0
#         print(f"价格: {price:.2f}, 仓位份数: {position}, 买入量: {buy_amount:.6f}")


# def compute_grid_positions(a, b, grid_num, max_loss):
#     """
#     计算出网格的仓位
#     :param a: 网格的最大值
#     :param b: 网格的最小值
#     :param grid_num: 网格的数量
#     :param max_loss: 最大亏损金额
#     :return:
#     """
#     # 计算每个网格的价格区间
#     grid_interval = (a - b) / grid_num
#
#     # 计算网格价格列表
#     grid_prices = [a - i * grid_interval for i in range(grid_num + 1)]
#     print(grid_prices)
#
#     # 计算每个网格买的份数 100x + 90x - 80*2x = max_loss
#     grid_amount = max_loss / (sum(grid_prices[:-1]) - 2 * grid_prices[-1])
#     print(grid_amount)
#
#     # 组合新的数据进行返回
#     grid_positions = []
#     i = 0
#     for price in grid_prices:
#         grid_positions.append({
#             'price': price,
#             'long_amount': 0 if i == grid_num else grid_amount * (i + 1),
#             'short_amount': 0 if i == 0 else grid_amount * (grid_num - i + 1),
#         })
#         i += 1
#     print(grid_positions)
#     return grid_positions
#
#
# def get_now_grid_index(grid_positions, price):
#     """
#     获取当前网格的索引
#     :param grid_positions:
#     :param price:
#     :return:
#     """
#     for index in range(len(grid_positions)):
#         print(grid_positions[index]['price'])
#         if price >= grid_positions[index]['price']:
#             return index
#     return 0
#
#
#
# if __name__ == '__main__':
#     # 参数设置
#     a = 1000  # 网格价格上限
#     b = 900  # 网格价格下限
#     grid_num = 3  # 网格数量
#     max_loss = 100  # 最大亏损金额
#
#     grid_position = compute_grid_positions(a, b, grid_num, max_loss)
#     a = get_now_grid_index(grid_position, 991)
#     print(a)

a = [{"price": 687.7209543440449, "long_amount": 0.0018473417275716698, "short_amount": 0},
     {"price": 684.1775941819501, "long_amount": 0.0036946834551433395, "short_amount": 0.0184734172757167},
     {"price": 680.6342340198553, "long_amount": 0.005542025182715009, "short_amount": 0.016626075548145026},
     {"price": 677.0908738577605, "long_amount": 0.007389366910286679, "short_amount": 0.014778733820573358},
     {"price": 673.5475136956657, "long_amount": 0.00923670863785835, "short_amount": 0.012931392093001688},
     {"price": 670.0041535335708, "long_amount": 0.011084050365430018, "short_amount": 0.011084050365430018},
     {"price": 666.460793371476, "long_amount": 0.012931392093001688, "short_amount": 0.00923670863785835},
     {"price": 662.9174332093812, "long_amount": 0.014778733820573358, "short_amount": 0.007389366910286679},
     {"price": 659.3740730472864, "long_amount": 0.016626075548145026, "short_amount": 0.005542025182715009},
     {"price": 655.8307128851916, "long_amount": 0.0184734172757167, "short_amount": 0.0036946834551433395},
     {"price": 652.2873527230968, "long_amount": 0, "short_amount": 0.0018473417275716698}]


if __name__ == '__main__':
    all_price = 0
    all_value = 0
    p_list = []
    for i in a:
        price = i['price']
        p_list.append(price)
        all_value += price * 0.0513
        print(price)
        all_price += price
    all_value -= a[-1]['price'] * 0.0513
    sell_value = a[-1]['price'] * 0.0513 * len(p_list[:-1])
    print(all_value)
    print(sell_value)
    print(all_price)
    print(all_price / len(a))

    buy_value = sum(p_list[:-1])
    sell_value = p_list[-1] * len(p_list[:-1])
    print(buy_value)
    print(sell_value)
    print(10 / (buy_value - sell_value))
