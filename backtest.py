import backtrader as bt
import datetime
import pandas as pd
import yfinance as yf

class MyStrategy(bt.Strategy):
    def __init__(self):
        self.ema50 = bt.indicators.EMA(period=50)
        self.rsi = bt.indicators.RSI(period=14)
        self.macd = bt.indicators.MACD()
        
        # Initialize variables to track long and short trade statistics
        self.long_trades = 0
        self.short_trades = 0
        self.long_profit = 0
        self.short_profit = 0
        self.long_loss = 0
        self.short_loss = 0

    def next(self):
        if len(self.data) < 2:
            return  
        
        last_close = self.data.close[-1]  # Use the previous close price
        prev_macd = self.macd.macd[-1]
        prev_signal = self.macd.signal[-1]
        curr_macd = self.macd.macd[0]
        curr_signal = self.macd.signal[0]
        
        long_condition = (
            last_close > self.ema50[0] and
            self.rsi[0] >= 50 and
            prev_macd <= prev_signal and
            curr_macd > curr_signal
        )
        
        short_condition = (
            last_close < self.ema50[0] and
            self.rsi[0] <= 50 and
            prev_macd >= prev_signal and
            curr_macd < curr_signal
        )
        
        cash = self.broker.get_cash()
        size = (cash * 0.8) / last_close  # Calculate position size
        size = round(size)
        if long_condition:
            # Record the trade, execute buy order
            self.buy(size=size)
            self.sell(price=last_close + 0.09, exectype=bt.Order.Limit)  # Take profit with limit order
            
            # Track the number of long trades
            self.long_trades += 1

        if short_condition:
            # Record the trade, execute sell order
            self.sell(size=size)
            self.buy(price=last_close - 0.09, exectype=bt.Order.Limit)  # Take profit with limit order
            self.buy(price=last_close + 0.11, exectype=bt.Order.Stop)  # Stop loss order
            
            # Track the number of short trades
            self.short_trades += 1

    def stop(self):
        # Display statistics at the end of the backtest
        print(f"--- Backtest Results ---")
        
        # Calculate the net profits for long and short trades
        long_net_profit = self.long_profit - self.long_loss
        short_net_profit = self.short_profit - self.short_loss
        
        print(f"Long Trades: {self.long_trades}")
        print(f"Total Long Profit: {self.long_profit}")
        print(f"Total Long Loss: {self.long_loss}")
        print(f"Net Long Profit: {long_net_profit}")
        
        print(f"Short Trades: {self.short_trades}")
        print(f"Total Short Profit: {self.short_profit}")
        print(f"Total Short Loss: {self.short_loss}")
        print(f"Net Short Profit: {short_net_profit}")



def run_backtest():
   # 下载数据
    df = yf.download('XRP-USD', start='2024-11-13', end='2025-02-13', interval='1h')
    #print(df.columns)
    # 将索引转换为列
    df = df.reset_index()

    # 将 MultiIndex 列名转换为单一列名
    df.columns = ['_'.join(col).strip() for col in df.columns.values]

    # 打印转换后的列名
    #print("转换后的列名:", df.columns)
    #print(df.head())
    # 清理日期列
    df['Datetime_'] = df['Datetime_'].astype(str)  # 确保日期列是字符串类型
    df['Datetime_'] = df['Datetime_'].str.replace(r'\+00:00', '', regex=True)  # 删除时区信息
    df['Datetime_'] = pd.to_datetime(df['Datetime_'], errors='coerce')  # 转换为日期时间格式
    df = df.dropna(subset=['Datetime_'])  # 删除无法转换为日期的行

    # 对数值列进行四舍五入，保留三位小数
    df = df.round({'Open_XRP-USD': 3, 'High_XRP-USD': 3, 'Low_XRP-USD': 3, 'Close_XRP-USD': 3, 'Volume_XRP-USD': 3})

    # 保存清理后的数据
    df.to_csv('cleaned_XRP_data.csv', index=False)

    # 加载数据到 backtrader
    data = bt.feeds.GenericCSVData(
        dataname='cleaned_XRP_data.csv',
        fromdate=pd.to_datetime('2024-11-13'),
        todate=pd.to_datetime('2025-02-13'),
        nullvalue=0.0,
        dtformat=('%Y-%m-%d %H:%M:%S'),  # 设置日期格式
        datetime=0,  # 日期列的索引（Datetime_）
        open=4,      # 开盘价列的索引（Open_XRP-USD）
        high=2,      # 最高价列的索引（High_XRP-USD）
        low=3,       # 最低价列的索引（Low_XRP-USD）
        close=1,     # 收盘价列的索引（Close_XRP-USD）
        volume=5,    # 成交量列的索引（Volume_XRP-USD）
        openinterest=-1  # 如果没有 openinterest，可以设置为 -1
    )

    # 创建 Cerebro 引擎
    cerebro = bt.Cerebro()

    # 添加数据
    cerebro.adddata(data)

    # 添加策略
    cerebro.addstrategy(MyStrategy)

    # 设置初始资金
    cerebro.broker.set_cash(200)

    # 运行回测
    cerebro.run()

    # 打印最终资金
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
if __name__ == '__main__':
    run_backtest()