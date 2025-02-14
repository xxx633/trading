import requests
import pandas as pd
import numpy as np
import sys
import os
import time
from datetime import datetime
# 添加项目根目录到系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import *

# 全局配置
EPIC = "XRPUSD"        # 交易品种
RESOLUTION = "HOUR"    # 交易周期
ATR_PERIOD = 14        # ATR周期
STOP_MULTIPLIER = 1.5  # 止损倍数

"""
#可以update order
class TradingState:
    def __init__(self):
        self.position = {
            "direction": None,  # 当前持仓方向（BUY/SELL）
            "dealId": None,
            "size": None
        }
        
        self.entry_price = None  # 入场价格
        self.stop_loss = None    # 止损价格
        self.initial_tp = 0      # 初始止盈价格
        self.trailing_tp = 0     # 动态止盈价格
        self.highest = -1        # 多单最高价
        self.lowest = 1000       # 空单最低价
        
    def reset(self):
        self.__init__()

# 实例化交易状态
trade_state = TradingState()
"""
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
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
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

def calculate_position_size(current_price, account_balance):
    """根据风险比例计算头寸规模"""
    risk_amount = account_balance * 0.8
    contract_size = risk_amount / round(current_price, 1)

    if contract_size < 1:
        print(f"⚠️ 计算的头寸规模 {contract_size} 小于最小交易规模 1")
        return 1
    
    return round(contract_size)

def generate_signal(df):
    """生成交易信号"""
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    long_condition = (
        (last_row["close"] > last_row["ema50"]) and
        (last_row["rsi"] >= 50) and
        (prev_row["macd"] <= prev_row["signal"]) and
        (last_row["macd"] > last_row["signal"])
    )

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

def execute_trade(direction, cst, token, df):
    """执行交易订单"""
    current_atr = df["atr"].iloc[-1]
    current_price = df["close"].iloc[-1]

    account = get_account_balance(cst, token)
    if not account:
        return

    size = calculate_position_size(current_price, account["balance"])
    if size <= 0:
        return
    
    if direction == "BUY":
        #stop_loss = current_price - 0.024 - current_atr * STOP_MULTIPLIER
        #stop_loss = False
        initial_tp = current_price + 0.012 + current_atr * STOP_MULTIPLIER * 1.3
    else:
        stop_loss = current_price + 0.024 + current_atr * STOP_MULTIPLIER
        initial_tp = current_price - 0.012 - current_atr * STOP_MULTIPLIER * 1.3

    order = {
        "epic": EPIC,
        "direction": direction,
        "size": size,
        "orderType": "MARKET",
        #"stopLevel": round(stop_loss, 3),
        "profitLevel": round(initial_tp, 3),
        "guaranteedStop": False,
        "oco":True 
    }
    if direction == "SELL":
        order["stopLevel"] = round(stop_loss, 3)

    response = requests.post(
        f"{BASE_URL}positions",
        headers={"CST": cst, "X-SECURITY-TOKEN": token},
        json=order
    )

    if response.status_code == 200:
        position_data = response.json()
        deal_reference = position_data.get("dealReference")

        if not deal_reference:
            print("❌ 订单失败: 未返回 dealReference")
            return

        deal_id = get_deal_id(deal_reference, cst, token)
        if not deal_id:
            print("❌ 订单失败: 无法获取 dealId")
            return
        """
        trade_state.position = {
            "direction": direction,
            "dealId": deal_id,
            "size": size
        }
        
        trade_state.entry_price = current_price
        trade_state.stop_loss = stop_loss
        trade_state.initial_tp = initial_tp
        trade_state.trailing_tp = initial_tp
        trade_state.highest = current_price if direction == "BUY" else None
        trade_state.lowest = current_price if direction == "SELL" else None
        """
        if direction == "BUY":
            print(f"✅ {direction} 数量: {size} | 买入价: {current_price+0.01:.2f} | 止盈: {initial_tp:.2f}")
        else:
            print(f"✅ {direction} 数量: {size} | 买出价: {current_price-0.01:.2f} | 止损: {stop_loss:.2f} | 止盈: {initial_tp:.2f}")
    else:
        print(f"❌ 订单失败: {response.status_code} - {response.text}")

"""
def check_exit_conditions(cst, token, df):
    if not trade_state.position or not trade_state.position["dealId"]:
        return

    current_price = df["close"].iloc[-1]
    current_atr = df["atr"].iloc[-1]

    if trade_state.position["direction"] == "BUY":
        trade_state.highest = max(trade_state.highest, current_price)
        trade_state.trailing_tp = trade_state.highest - current_atr * STOP_MULTIPLIER
        final_tp = max(trade_state.initial_tp, trade_state.trailing_tp)
        if current_price <= trade_state.stop_loss:
            exit_reason = "触发止损"
        elif current_price >= final_tp:
            exit_reason = "达到止盈"
        else:
            exit_reason = None
    elif trade_state.position["direction"] == "SELL":
        trade_state.lowest = min(trade_state.lowest, current_price)
        trade_state.trailing_tp = trade_state.lowest + current_atr * STOP_MULTIPLIER
        final_tp = min(trade_state.initial_tp, trade_state.trailing_tp)
        if current_price >= trade_state.stop_loss:
            exit_reason = "触发止损"
        elif current_price <= final_tp:
            exit_reason = "达到止盈"
        else:
            exit_reason = None
    else:
        exit_reason = None

    if exit_reason:
        close_all_positions(cst, token)
        print(f"🚪 平仓原因: {exit_reason} | 价格: {current_price:.2f}")


def close_all_positions(cst, security_token):
    # 获取所有当前仓位
    positions = get_all_positions(cst, security_token)
    
    if not positions:
        print("⚠️ 无持仓可平")
        return False
    
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    success = True
    
    for item in positions:
        position = item.get('position', {})
        deal_id = position.get('dealId')
        
        if not deal_id:
            print(f"❌ 未找到仓位的 dealId: {position}")
            success = False
            continue
        
        url = BASE_URL + f"positions/{deal_id}"
        response = requests.delete(url, headers=headers)
        
        if response.status_code == 200:
            print(f"🔵 成功平仓，dealId: {deal_id}")
        else:
            print(f"❌ 平仓失败 dealId {deal_id}: {response.text}")
            success = False
    
    return success
"""
def get_positions(cst, security_token):
    url = BASE_URL + "positions"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get('positions', [])
    else:
        print(f"❌ 获取持仓信息失败: {response.text}")
        return []


def mta(cst, token):
    if get_positions(cst, token):
        print("🔵 当前已有持仓，跳过信号检查")
        return

    df = get_market_data(cst, token, EPIC, RESOLUTION)
    if df is None:
        print("❌ K线数据为空，无法计算指标")
        return

    df = calculate_indicators(df)
    if df is None:
        return
    
    # 生成信号
    signal = generate_signal(df)
    if signal:
        #trade_state.reset()
        execute_trade(signal, cst, token, df)