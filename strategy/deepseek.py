import requests
import pandas as pd
import numpy as np
import sys
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import json 


#目前不可用



# 全局配置
EPIC = "XRPUSD"
RESOLUTIONS = {
    'lower': 'MINUTE',
    'higher': 'MINUTE_5'
}
RISK_PERCENT = 5
MIN_SIZE=1
# 2倍杠杆 保证金50%
LEVERAGE=1

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import *

class EnhancedTradingState:
    """增强版交易状态管理"""
    def __init__(self):
        self.position: Optional[str] = None
        self.entry_price: Optional[float] = None
        self.entry_time: Optional[datetime] = None
        self.adaptive_sl: Optional[float] = None
        self.initial_sl: Optional[float] = None
        self.trend_strength: float = 0.0
        self.open_orders: list = []
        self.consecutive_loss: int = 0
        self.dynamic_params: Dict[str, any] = {
            'current_volatility': 0.0,
            'market_regime': 'neutral',
            'profit_ratio': 2.0,
            'stop_multiplier': 1.5
        }

    def reset(self):
        self.__init__()

trade_state = EnhancedTradingState()

class PerformanceAnalyzer:
    """绩效分析模块"""
    def __init__(self):
        self.trade_log: list = []
    
    def record_trade(self, entry: float, exit: float, size: float, 
                    direction: str, duration: float, volatility: float):
        profit = (exit - entry) * size * (1 if direction == "BUY" else -1)
        self.trade_log.append({
            'entry_time': trade_state.entry_time,
            'exit_time': datetime.now(),
            'duration': duration,
            'return': profit,
            'volatility': volatility,
            'market_regime': trade_state.dynamic_params['market_regime']
        })
    
    def generate_report(self):
        if not self.trade_log:
            return "No trades recorded"
            
        df = pd.DataFrame(self.trade_log)
        report = {
            'total_trades': len(df),
            'win_rate': len(df[df['return'] > 0]) / len(df),
            'avg_return': df['return'].mean(),
            'max_drawdown': df['return'].cumsum().min(),
            'sharpe_ratio': df['return'].mean() / df['return'].std(),
            'by_regime': df.groupby('market_regime')['return'].mean()
        }
        return report

analyzer = PerformanceAnalyzer()

# 工具函数 ------------------------------------------------------------

def get_historical_data(cst: str, token: str, epic: str, resolution: str, 
                       count: int) -> Optional[pd.DataFrame]:
    """获取历史数据（支持多时间框架）"""
    try:
        params = {
            'resolution': resolution,
            'max': count,
            'pageSize': 0
        }
        response = requests.get(
            f"{BASE_URL}prices/{epic}",
            headers={"CST": cst, "X-SECURITY-TOKEN": token},
            params=params
        )
        if response.status_code == 200:
            #print(json.dumps(response.json(), indent=4))
            data = response.json()['prices']
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['snapshotTime'], utc=True)
            df.set_index('timestamp', inplace=True)

            # 取 `bid` 值
            df['open'] = df['openPrice'].apply(lambda x: x['bid'])
            df['high'] = df['highPrice'].apply(lambda x: x['bid'])
            df['low'] = df['lowPrice'].apply(lambda x: x['bid'])
            df['close'] = df['closePrice'].apply(lambda x: x['bid'])
            df['volume'] = df['lastTradedVolume']  # 提取成交量

            df = df[['open', 'high', 'low', 'close', 'volume']]
            return df.astype(float)
        print(f"数据获取失败: {response.text}")
        return None
    except Exception as e:
        print(f"获取数据异常: {str(e)}")
        return None

def validate_market_data(df: pd.DataFrame) -> bool:
    """校验市场数据完整性"""
    required_columns = ['open','high','low','close','volume']
    if not all(col in df.columns for col in required_columns):
        print("数据缺失必要列")
        return False
    if df.isnull().values.any():
        print("数据包含空值")
        return False
    if (df['close'] <= 0).any():
        print("存在无效价格")
        return False
    return True

# 指标计算 ------------------------------------------------------------

# EMA参数动态调整可优化
def calculate_dynamic_ema_params(volatility_ratio: float) -> Tuple[int, int]:
    """基于波动率矩阵计算EMA参数"""
    matrix = {
        (0.0, 0.01): (30, 100),
        (0.01, 0.03): (50, 150),
        (0.03, 0.05): (20, 80)
    }
    for (low, high), params in matrix.items():
        if low <= volatility_ratio < high:
            return params
    return (50, 100)  # 默认值

def calculate_enhanced_indicators(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """增强指标计算"""
    try:
        
        # 波动率系统
        df['prev_close'] = df['close'].shift(1)
        df['tr'] = np.maximum.reduce([
            df['high'] - df['low'],
            abs(df['high'] - df['prev_close']),
            abs(df['low'] - df['prev_close'])
        ])

        df['atr'] = df['tr'].rolling(14).mean()


        volatility_ratio = df['atr'].iloc[-1] / df['close'].iloc[-1]
        ema_short,ema_long = calculate_dynamic_ema_params(volatility_ratio)
    
        df['ema_dynamic_short'] = df['close'].ewm(span=ema_short).mean()
        df['ema_dynamic_long'] = df['close'].ewm(span=ema_long).mean()
        
        
        # MACD系统
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = df['ema12'] - df['ema26']
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['signal']
        
        # ADX趋势强度
        high, low, close = df['high'], df['low'], df['close']
        plus_dm = high.diff()
        minus_dm = low.diff().abs()
        trur = df['tr'].rolling(14).sum()
        plus_di = 100 * (plus_dm.rolling(14).sum() / trur)
        minus_di = 100 * (minus_dm.rolling(14).sum() / trur)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        df['adx'] = dx.rolling(14).mean()
        
        # 成交量分析
        df['vol_ma'] = df['volume'].rolling(20).mean()
        
        # 价格通道
        df['upper_band'] = df['ema_dynamic_short'] + df['atr'] * 1.5
        df['lower_band'] = df['ema_dynamic_short'] - df['atr'] * 1.5
        
        return df.dropna()
    except Exception as e:
        print(f"指标计算失败: {str(e)}")
        return None

# 信号生成 ------------------------------------------------------------

def is_pinbar(row: pd.Series) -> bool:
    """识别Pin Bar形态"""
    body_size = abs(row['close'] - row['open'])
    if body_size == 0:
        return None
    upper_wick = row['high'] - max(row['close'], row['open'])
    lower_wick = min(row['close'], row['open']) - row['low']
    
    
    if lower_wick > 2 * body_size and upper_wick < body_size / 2:
        return "BUY"
    elif upper_wick > 2 * body_size and lower_wick < body_size / 2:
        return "SELL"
    return None

def generate_signal(lower_df: pd.DataFrame, higher_df: pd.DataFrame) -> Tuple[Optional[str], float]:
    """
    根据低时间框架与高时间框架的数据生成交易信号。
    返回一个元组：(signal, adx)
      - signal: "BUY" 表示做多，"SELL" 表示做空，None 表示没有信号。
      - adx: 当前低时间框架的ADX值，用于后续仓位计算。
    """
    try:
        # 取两个时间框架的最新一根K线数据
        latest_lower = lower_df.iloc[-1]
        latest_higher = higher_df.iloc[-1]
        
        # 使用低时间框架的ADX作为信号强度指标
        adx = latest_lower['adx']
        
        # 初始化信号标志
        buy_signal = False
        sell_signal = False
        
        # 核心条件：EMA和MACD
        ema_bullish = latest_lower['ema_dynamic_short'] > latest_lower['ema_dynamic_long']
        ema_bearish = latest_lower['ema_dynamic_short'] < latest_lower['ema_dynamic_long']
        macd_bullish = latest_lower['macd_hist'] > 0
        macd_bearish = latest_lower['macd_hist'] < 0
        
        # 辅助条件：成交量、价格位置、ADX
        volume_confirm = latest_lower['volume'] > latest_lower['vol_ma']
        price_above_ema = latest_lower['close'] > latest_lower['ema_dynamic_short']
        price_below_ema = latest_lower['close'] < latest_lower['ema_dynamic_short']
        strong_trend = adx > 30
        
        # 动态调整多时间框架过滤
        higher_trend_up = latest_higher['ema_dynamic_short'] > latest_higher['ema_dynamic_long']
        higher_trend_down = latest_higher['ema_dynamic_short'] < latest_higher['ema_dynamic_long']
        
        # 条件1：基于动态EMA和MACD的信号
        if (ema_bullish and macd_bullish) or (ema_bearish and macd_bearish):
            # 趋势市：放宽高时间框架过滤，允许短期回调入场
            if strong_trend:
                buy_signal = ema_bullish and macd_bullish and price_above_ema
                sell_signal = ema_bearish and macd_bearish and price_below_ema
            # 震荡市：要求高时间框架方向一致，并严格成交量验证
            else:
                buy_signal = (
                    ema_bullish and macd_bullish and 
                    higher_trend_up and price_above_ema and 
                    volume_confirm
                )
                sell_signal = (
                    ema_bearish and macd_bearish and 
                    higher_trend_down and price_below_ema and 
                    volume_confirm
                )
        
        # 条件2：检查Pin Bar形态，提供额外的入场提示
        pinbar_direction = is_pinbar(latest_lower)
        if pinbar_direction == "BUY":
            buy_signal = buy_signal or (price_above_ema and volume_confirm)
        elif pinbar_direction == "SELL":
            sell_signal = sell_signal or (price_below_ema and volume_confirm)
        
        # 最终信号生成
        if buy_signal and not sell_signal:
            return ("BUY", adx)
        elif sell_signal and not buy_signal:
            return ("SELL", adx)
        else:
            return (None, adx)

    except Exception as e:
        print(f"信号生成错误: {str(e)}")
        return None, 0.0


# 订单管理 ------------------------------------------------------------

class OrderManager:
    """订单执行管理"""
    def __init__(self, cst: str, token: str):
        self.cst = cst
        self.token = token
        self.max_retry = 3
        
    def execute_order(self, order: Dict) -> Optional[str]:
        """执行订单"""
        for attempt in range(self.max_retry):
            try:
                response = requests.post(
                    f"{BASE_URL}positions",
                    headers={"CST": self.cst, "X-SECURITY-TOKEN": self.token},
                    json=order,
                    timeout=5
                )
                if response.status_code == 200:
                    return response.json().get("dealReference")
                if response.status_code == 429:
                    sleep_time = 2 ** attempt
                    print(f"API限速，等待{sleep_time}秒后重试")
                    time.sleep(sleep_time)
            except requests.exceptions.RequestException as e:
                print(f"网络错误: {str(e)}")
        return None
        
    def close_position(self, deal_id: str, size: float):
        """平仓操作"""
        direction = "SELL" if trade_state.position == "BUY" else "BUY"
        order = {
            "dealId": deal_id,
            "direction": direction,
            "size": size,
            "orderType": "MARKET"
        }
        return self.execute_order(order)

# 风险管理 ------------------------------------------------------------

def dynamic_position_sizing(current_price: float, atr: float, 
                           balance: float, adx: float) -> float:
    """动态仓位计算"""
    try:
        # 波动率因子
        volatility_factor = np.interp(atr/current_price*100, [0.5, 2.0], [1.5, 0.5])
        
        # 趋势强度因子
        trend_factor = np.interp(adx, [25, 50], [0.8, 1.2])
        
        # 市场状态因子
        regime_factor = 1.0
        if trade_state.dynamic_params['market_regime'] == 'trending':
            regime_factor = 1.5
        elif trade_state.dynamic_params['market_regime'] == 'ranging':
            regime_factor = 0.5
            
        adjusted_risk = RISK_PERCENT * volatility_factor * trend_factor * regime_factor
        risk_amount = max(balance * adjusted_risk / 100, 0)
        
        dollar_risk = atr * current_price * trade_state.dynamic_params['stop_multiplier']
        size = risk_amount / dollar_risk
        

        # 交易量限制 
        size = max(round(size, 2), MIN_SIZE)  # 平台最小交易量
        max_size = (balance * LEVERAGE)/current_price  
        return min(size, max_size)
    except Exception as e:
        print(f"仓位计算错误: {str(e)}")
        return MIN_SIZE

def update_market_regime(df: pd.DataFrame):
    """更新市场状态"""
    atr = df['atr'].iloc[-1]
    close_std = df['close'].rolling(20).std().iloc[-1]
    
    trade_state.dynamic_params['current_volatility'] = atr / df['close'].iloc[-1]
    
    if (atr > close_std * 1.5) and (df['adx'].iloc[-1] > 30):
        trade_state.dynamic_params['market_regime'] = 'trending'
        trade_state.dynamic_params['profit_ratio'] = 3.0
        trade_state.dynamic_params['stop_multiplier'] = 1.2
    elif (atr < close_std * 0.7) and (df['adx'].iloc[-1] < 20):
        trade_state.dynamic_params['market_regime'] = 'ranging'
        trade_state.dynamic_params['profit_ratio'] = 1.5
        trade_state.dynamic_params['stop_multiplier'] = 2.0
    else:
        trade_state.dynamic_params['market_regime'] = 'neutral'
        trade_state.dynamic_params['profit_ratio'] = 2.0
        trade_state.dynamic_params['stop_multiplier'] = 1.5

# 主交易逻辑 ----------------------------------------------------------

def deepseek(cst: str, token: str):
    """执行完整交易周期"""
    try:
        # 获取数据
        lower_df = get_historical_data(cst, token, EPIC, RESOLUTIONS['lower'], 200)
        higher_df = get_historical_data(cst, token, EPIC, RESOLUTIONS['higher'], 100)
        
        if not validate_market_data(lower_df) or not validate_market_data(higher_df):
            return
            
        # 计算指标
        lower_df = calculate_enhanced_indicators(lower_df)
        higher_df = calculate_enhanced_indicators(higher_df)
        
        # 更新市场状态
        update_market_regime(lower_df)
        
        # 持仓管理
        if trade_state.position:
            manage_open_position(lower_df, cst, token)
        else:
            generate_new_trade(lower_df, higher_df, cst, token)
    except Exception as e:
        print(f"交易周期错误: {str(e)}")

def manage_open_position(df: pd.DataFrame, cst: str, token: str):
    """持仓管理"""
    current_price = df['close'].iloc[-1]
    order_mgr = OrderManager(cst, token)
    
    # 检查最大持仓时间
    #hold_time = (datetime.now() - trade_state.entry_time).total_seconds() / 3600
    #if hold_time >= MAX_HOLD_HOURS:
        #print("达到最大持仓时间，平仓")
        #close_all_positions(order_mgr)
        #return
    
    # 更新动态止损
    new_sl = calculate_dynamic_sl(df)
    trade_state.adaptive_sl = new_sl
    
    # 检查止损
    if check_sl_hit(current_price, new_sl):
        print("触发止损，平仓")
        close_all_positions(order_mgr)
        return
    
    # 移动止损到盈亏平衡点
    if check_profit_protection(current_price):
        print("移动止损到盈亏平衡点")
        trade_state.adaptive_sl = trade_state.entry_price
    
    # 部分止盈
    check_partial_take_profit(current_price, order_mgr)

def generate_new_trade(lower_df: pd.DataFrame, higher_df: pd.DataFrame, 
                      cst: str, token: str):
    """生成新交易"""
    signal, adx = generate_signal(lower_df, higher_df)
    if not signal:
        return
        
    current_price = lower_df['close'].iloc[-1]
    atr = lower_df['atr'].iloc[-1]
    
    # 获取账户余额
    account = get_account_balance(cst, token)
    if not account:
        return
        
    # 计算仓位
    size = dynamic_position_sizing(current_price, atr, account['balance'], adx)
    if size <=0:
        return
        
    # 执行交易
    order_mgr = OrderManager(cst, token)
    execute_trade(signal, size, current_price, atr, order_mgr)

# 其他辅助函数（因篇幅限制，部分函数需根据实际情况实现）---------------
def calculate_dynamic_sl(df: pd.DataFrame) -> float:
    """计算动态止损"""
    if trade_state.position == "BUY":
        return max(
            trade_state.adaptive_sl,
            df['low'].rolling(3).min().iloc[-1],
            df['close'].iloc[-1] - 2*df['atr'].iloc[-1]
        )
    else:
        return min(
            trade_state.adaptive_sl,
            df['high'].rolling(3).max().iloc[-1],
            df['close'].iloc[-1] + 2*df['atr'].iloc[-1]
        )

def check_sl_hit(current_price: float, sl: float) -> bool:
    """检查是否触发止损"""
    if trade_state.position == "BUY":
        return current_price <= sl
    return current_price >= sl

def check_profit_protection(current_price: float) -> bool:
    """检查盈利保护条件"""
    risk = abs(trade_state.entry_price - trade_state.initial_sl)
    profit = abs(current_price - trade_state.entry_price)
    return profit >= risk

def check_partial_take_profit(current_price: float, order_mgr: OrderManager):
    """部分止盈检查"""
    for order in list(trade_state.open_orders):
        tp_price = order['tp_level']
        if ((trade_state.position == "BUY" and current_price >= tp_price) or
            (trade_state.position == "SELL" and current_price <= tp_price)):
            order_mgr.close_position(order['dealId'], order['size'])
            trade_state.open_orders.remove(order)

def close_all_positions(order_mgr: OrderManager):
    """平掉所有仓位"""
    for order in trade_state.open_orders:
        order_mgr.close_position(order['dealId'], order['size'])
    trade_state.reset()

def get_deal_id(deal_ref: str,order_mgr: OrderManager) -> Optional[str]:
    """获取交易ID"""
    for _ in range(3):
        response = requests.get(
            f"{BASE_URL}confirms/{deal_ref}",
            headers={"CST": order_mgr.cst, "X-SECURITY-TOKEN": order_mgr.token}
        )
        if response.status_code == 200 and response.json().get("dealStatus") == "ACCEPTED":
            return response.json().get("dealId")
        time.sleep(1)
    print("获取dealId失败")
    return None

def execute_trade(signal: str, size: float, price: float, 
                 atr: float, order_mgr: OrderManager):
    """执行交易"""
    try:
        # 分三笔下单
        base_size = round(size / 3, 2)
        levels = [1.5, 3.0, 5.0]  # ATR倍数
        
        for i, mult in enumerate(levels):
            tp_price = price + (mult * atr) if signal == "BUY" else price - (mult * atr)
            order = {
                "epic": EPIC,
                "direction": signal,
                "size": base_size,
                "orderType": "MARKET",
                "stopDistance": round(2 * atr, 4),
                "profitDistance": round(abs(tp_price - price), 4),
                "guaranteedStop": False
            }
            deal_ref = order_mgr.execute_order(order)
            if deal_ref:
                deal_id = get_deal_id(deal_ref, order_mgr)
                if (i == 0) and (not deal_id):  # 确保首单成交
                    return
                if deal_id:
                    trade_state.open_orders.append({
                        "dealId": deal_id,
                        "tp_level": tp_price,
                        "size": base_size
                    })
        # 更新交易状态
        trade_state.position = signal
        trade_state.entry_price = price
        trade_state.initial_sl = price - (2 * atr) if signal == "BUY" else price + (2 * atr)
        trade_state.adaptive_sl = trade_state.initial_sl
        trade_state.entry_time = datetime.now()
        
    except Exception as e:
        print(f"执行交易失败: {str(e)}")
