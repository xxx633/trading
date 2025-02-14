
import backtrader as bt
import datetime
import pandas as pd
import yfinance as yf

class MACDRSIStrategy(bt.Strategy):
    params = (
        ('size',10),  
        ('point_spread', 0.012),  
    )
    def __init__(self):
        # 初始化技术指标
        self.macd = bt.ind.MACD()
        self.macd_cross = bt.ind.CrossOver(self.macd.macd, self.macd.signal)  # 金叉死叉
        self.rsi = bt.ind.RSI(self.data.close, period=14)
        self.ema200 = bt.ind.EMA(period=50)
        self.atr = bt.ind.ATR(period=14)
        
        self.active_order = None  # 跟踪当前活跃订单
        self.is_opening = False   # 标记是否开仓操作

    def next(self):
        # 如果有未完成订单或已有持仓，则直接返回
        if self.active_order or self.position:
            return

        # 做多条件
        long_condition = (
            self.macd_cross[0] > 0 and
            self.rsi[0] >= 50 and
            self.data.close[0] > self.ema200[0]
        )

        # 做空条件
        short_condition = (
            self.macd_cross[0] < 0 and
            self.rsi[0] <= 50 and
            self.data.close[0] < self.ema200[0]
        )

        if long_condition:
            self.active_order = self.buy(size=self.p.size)
            self.is_opening = True
            
            # 计算止损止盈价格
            entry_price = self.data.close[0]
            atr_value = self.atr[0]
            stop_loss = entry_price - 1.5 * atr_value
            take_profit = entry_price + 2 * atr_value
            
            # 挂止损止盈单
            self.sell(exectype=bt.Order.Stop, price=stop_loss, size=self.p.size, parent=self.active_order)
            self.sell(exectype=bt.Order.Limit, price=take_profit, size=self.p.size, parent=self.active_order)

        elif short_condition:
            self.active_order = self.sell(size=self.p.size)
            self.is_opening = True
            
            # 计算止损止盈价格
            entry_price = self.data.close[0]
            atr_value = self.atr[0]
            stop_loss = entry_price + 1.5 * atr_value
            take_profit = entry_price - 2 * atr_value
            
            # 挂止损止盈单
            self.buy(exectype=bt.Order.Stop, price=stop_loss, size=self.p.size, parent=self.active_order)
            self.buy(exectype=bt.Order.Limit, price=take_profit, size=self.p.size, parent=self.active_order)

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if self.is_opening:
                # 扣除点差成本
                cost = self.p.point_spread * order.executed.size
                self.broker.add_cash(-cost)
                self.is_opening = False
                
            self.active_order = None  # 重置订单跟踪

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.active_order = None
            self.is_opening = False

def run_backtest():
   # 下载数据
    df = yf.download('XRP-USD', start='2024-11-13', end='2025-02-13', interval='1h')

    # 将索引转换为列
    df = df.reset_index()

    # 将 MultiIndex 列名转换为单一列名
    df.columns = ['_'.join(col).strip() for col in df.columns.values]

    # 打印转换后的列名
    #print("转换后的列名:", df.columns)

    # 清理日期列
    df['Datetime_'] = df['Datetime_'].astype(str)  # 确保日期列是字符串类型
    df['Datetime_'] = df['Datetime_'].str.replace(r'\+00:00', '', regex=True)  # 删除时区信息
    df['Datetime_'] = pd.to_datetime(df['Datetime_'], errors='coerce')  # 转换为日期时间格式
    df = df.dropna(subset=['Datetime_'])  # 删除无法转换为日期的行

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
    cerebro.addstrategy(MACDRSIStrategy)

    # 设置初始资金
    cerebro.broker.set_cash(1000)

    # 运行回测
    cerebro.run()

    # 打印最终资金
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())

if __name__ == '__main__':
    run_backtest()