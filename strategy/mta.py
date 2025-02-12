import requests
import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# 添加项目根目录到系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import *

# 全局配置
EPIC = "XRPUSD"        # 交易品种
RESOLUTION = "HOUR"  # 交易周期
RISK_PERCENT = 1       # 单笔风险比例（账户余额的1%）
ATR_PERIOD = 14        # ATR周期
STOP_MULTIPLIER = 1.5  # 止损倍数
PROFIT_RATIO = 2       # 盈亏比

class TradingState:
    """交易状态管理类"""
    def __init__(self):
        self.position = None  # 当前持仓方向（BUY/SELL）
        self.entry_price = None  # 入场价格
        self.stop_loss = None  # 止损价格
        self.initial_tp = None  # 初始止盈价格
        self.trailing_tp = None  # 动态止盈价格
        self.highest = None  # 多单最高价
        self.lowest = None  # 空单最低价

    def reset(self):
        """重置交易状态"""
        self.__init__()

# 实例化交易状态
trade_state = TradingState()

def calculate_indicators(df):
    """计算技术指标"""
    # 50 EMA
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

    # MACD (12, 26, 9)
    df["ema12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema26"] = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = df["ema12"] - df["ema26"]
    df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    # RSI (14)
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # ATR (ATR_PERIOD)
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(df['high'] - df['low'],
                          np.abs(df['high'] - df['prev_close']),
                          np.abs(df['low'] - df['prev_close']))
    df['atr'] = df['tr'].rolling(ATR_PERIOD).mean()
    df.drop(columns=['prev_close', 'tr'], inplace=True)

    return df

def calculate_position_size(current_price, atr_value, account_balance):
    """根据风险比例计算头寸规模"""
    min_size=1
    risk_amount = account_balance * RISK_PERCENT / 100
    dollar_risk = atr_value * current_price * STOP_MULTIPLIER
    contract_size = risk_amount / dollar_risk

    # 确保头寸规模不小于最小交易规模
    if contract_size < min_size:
        print(f"⚠️ 计算的头寸规模 {contract_size} 小于最小交易规模 {min_size}，已调整为 {min_size}")
        return min_size
    
    return round(contract_size, 2)

def generate_signal(df):
    """生成交易信号"""
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    # 做多条件
    long_condition = (
        (last_row["close"] > last_row["ema50"]) and
        (last_row["rsi"] >= 50) and
        (prev_row["macd"] <= prev_row["signal"]) and
        (last_row["macd"] > last_row["signal"])
    )

    # 做空条件
    short_condition = (
        (last_row["close"] < last_row["ema50"]) and
        (last_row["rsi"] <= 50) and
        (prev_row["macd"] >= prev_row["signal"]) and
        (last_row["macd"] < last_row["signal"])
    )

    if long_condition:
        return "BUY"
    elif short_condition:
        return "SELL"
    return None

# ======== 交易执行 ========
def execute_trade(direction, cst, token,df):
    """执行交易订单"""

    current_atr = df["atr"].iloc[-1]
    current_price = df["close"].iloc[-1]

    # 获取账户余额
    account = get_account_balance(cst, token)
    if not account:
        return

    # 计算头寸规模
    size = calculate_position_size(current_price, current_atr, account["balance"])
    if size <= 0:
        return
    
    # 设置止损止盈
    if direction == "BUY":
        stop_loss = current_price - current_atr * STOP_MULTIPLIER
        initial_tp = current_price + current_atr * STOP_MULTIPLIER * PROFIT_RATIO
    else:
        stop_loss = current_price + current_atr * STOP_MULTIPLIER
        initial_tp = current_price - current_atr * STOP_MULTIPLIER * PROFIT_RATIO

    # 创建订单
    order = {
        "epic": EPIC,
        "direction": direction,
        "size": size,
        "orderType": "MARKET",
        "stopDistance": round(stop_loss, 2),
        "profitDistance": round(initial_tp, 2),
        "currencyCode": account["currency"],
        "guaranteedStop": False
    }

    # 发送订单请求
    response = requests.post(
        f"{BASE_URL}positions",
        headers={"CST": cst, "X-SECURITY-TOKEN": token},
        json=order
    )

    if response.status_code == 200:
        position_data = response.json()
        trade_state.position = {
            "direction": direction,
            "dealId": position_data["dealId"],
            "size": size
        }
        trade_state.entry_price = current_price
        trade_state.stop_loss = stop_loss
        trade_state.initial_tp = initial_tp
        trade_state.trailing_tp = initial_tp
        trade_state.highest = current_price if direction == "BUY" else None
        trade_state.lowest = current_price if direction == "SELL" else None
        print(f"✅ {direction}订单成功 | 数量: {size} | 止损: {stop_loss:.2f} | 初始止盈: {initial_tp:.2f}")
    else:
        print(f"❌ 订单失败: {response.text}")

def check_exit_conditions(cst, token,df):
    """检查退出条件"""
    if not trade_state.position:
        return

    current_price = df["close"].iloc[-1]
    current_atr = df["atr"].iloc[-1]

    # 更新动态止盈
    if trade_state.position == "BUY":
        trade_state.highest = max(trade_state.highest, current_price)
        trade_state.trailing_tp = trade_state.highest - current_atr * STOP_MULTIPLIER
        final_tp = max(trade_state.initial_tp, trade_state.trailing_tp)
    else:
        trade_state.lowest = min(trade_state.lowest, current_price)
        trade_state.trailing_tp = trade_state.lowest + current_atr * STOP_MULTIPLIER
        final_tp = min(trade_state.initial_tp, trade_state.trailing_tp)

    # 退出条件判断
    exit_reason = None
    if trade_state.position == "BUY":
        if current_price <= trade_state.stop_loss:
            exit_reason = "触发止损"
        elif current_price >= final_tp:
            exit_reason = "达到止盈"
    elif trade_state.position == "SELL":
        if current_price >= trade_state.stop_loss:
            exit_reason = "触发止损"
        elif current_price <= final_tp:
            exit_reason = "达到止盈"

    # 执行平仓
    if exit_reason:
        close_position(cst, token)
        print(f"🚪 平仓原因: {exit_reason} | 价格: {current_price:.2f}")

def close_position(cst, token):
    """平仓函数"""
    if not isinstance(trade_state.position, dict):
        return

    url = f"{BASE_URL}positions/otc"
    payload = {
        "dealId": trade_state.position["dealId"],
        "direction": "SELL" if trade_state.position == "BUY" else "BUY",
        "size": trade_state.position["size"],
        "orderType": "MARKET"
    }
    response = requests.post(
        url,
        headers={"CST": cst, "X-SECURITY-TOKEN": token},
        json=payload
    )
    if response.status_code == 200:
        print("✅ 平仓成功")
        trade_state.reset()
    else:
        print("❌ 平仓失败:", response.json())

def mta(cst, token):
    df = get_market_data(cst, token, EPIC, RESOLUTION)
    if df is None:
        print("❌ K线数据为空，无法计算指标")
        return

    df = calculate_indicators(df)

    # 检查现有持仓
    if trade_state.position:
        check_exit_conditions(cst, token,df)
    else:
        # 生成交易信号
        signal = generate_signal(df)
        if signal:
            execute_trade(signal, cst, token,df)