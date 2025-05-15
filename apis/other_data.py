import yfinance as yf
from datetime import datetime


def get_nasdaq100_data():
    """
    获取纳斯达克100指数（^NDX）最新数据
    返回包含时间戳和关键指标的字典
    """
    try:
        # 获取最近5分钟数据（确保能获取到最新报价）
        data = yf.download(
            tickers='^NDX',
            period='1d',
            interval='1m',
            progress=False
        )

        if not data.empty:
            latest = data.iloc[-1]
            return {
                'symbol': 'NASDAQ100',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'open': round(latest['Open'], 2),
                'high': round(latest['High'], 2),
                'low': round(latest['Low'], 2),
                'close': round(latest['Close'], 2),
                'volume': int(latest['Volume'])
            }
        return None
    except Exception as e:
        print(f"获取纳斯达克100数据失败: {str(e)}")
        return None


def get_dollar_index_data():
    """
    获取美元指数（DX-Y.NYB）最新数据
    返回包含时间戳和关键指标的字典
    """
    try:
        # 获取最近5分钟数据
        data = yf.download(
            tickers='DX-Y.NYB',
            period='1d',
            interval='1m',
            progress=False
        )

        if not data.empty:
            latest = data.iloc[-1]
            return {
                'symbol': 'USDINDEX',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'open': round(latest['Open'], 2),
                'high': round(latest['High'], 2),
                'low': round(latest['Low'], 2),
                'close': round(latest['Close'], 2),
                'volume': int(latest['Volume'])
            }
        return None
    except Exception as e:
        print(f"获取美元指数数据失败: {str(e)}")
        return None


# 使用示例 ---------------------------------------------------
if __name__ == "__main__":
    # 获取纳斯达克数据
    ndx_data = get_nasdaq100_data()
    if ndx_data:
        print("纳斯达克100最新数据：")
        print(f"时间：{ndx_data['timestamp']}")
        print(f"收盘价：{ndx_data['close']} 成交量：{ndx_data['volume']:,}")

    # 获取美元指数数据
    usd_data = get_dollar_index_data()
    if usd_data:
        print("\n美元指数最新数据：")
        print(f"时间：{usd_data['timestamp']}")
        print(f"收盘价：{usd_data['close']} 成交量：{usd_data['volume']:,}")