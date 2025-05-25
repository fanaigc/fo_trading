
def calc_geometric_grid_prices(price_high, price_low, grid_num):
    # 计算公比 r
    r = (price_low / price_high) ** (1 / grid_num)

    # 计算每一层网格的价格（等比数列）
    grid_prices = [price_high * (r ** i) for i in range(grid_num + 1)]

    return grid_prices

if __name__ == '__main__':

    a = 10000  # 最高价
    b = 9000   # 最低价
    grid_num = 10

    geometric_prices = calc_geometric_grid_prices(a, b, grid_num)
    print(geometric_prices)
    for i, price in enumerate(geometric_prices):
        print(f"第{i}层网格价格：{round(price, 2)}")