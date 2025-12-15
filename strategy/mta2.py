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
EPIC = "XRPUSD"
RESOLUTION = "HOUR"
ATR_PERIOD = 14
#STOP_MULTIPLIER = 3

# === 技术指标计算 ===
def calculate_indicators(df):
    df["ema13"] = df["close"].ewm(span=13, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()

    # ATR
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(df['high'] - df['low'],
                          np.abs(df['high'] - df['prev_close']),
                          np.abs(df['low'] - df['prev_close']))
    df['atr'] = df['tr'].rolling(ATR_PERIOD).mean()

    return df

# === 仓位计算 ===
def calculate_position_size(current_price, account_balance):
    rounded_price=round(current_price, 1)
    
    contract_size=(account_balance*0.67)/rounded_price
        
    if contract_size < 1:
        print(f"⚠️ 计算的头寸规模 {contract_size} 小于最小交易规模 1")
        return 1
    
    return round(contract_size)

# === 信号生成（加入金叉/死叉） ===
def generate_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # 金叉：ema13 上穿 ema21
    long_cond = last["ema13"] > last["ema21"] and prev["ema13"] <= prev["ema21"]

    # 死叉：ema13 下穿 ema21
    #short_cond = last["ema13"] < last["ema21"] and prev["ema13"] >= prev["ema21"]

    if long_cond:
        return "BUY"
    #elif short_cond:
        #return "SELL"
    return None

# === 执行下单 ===
def execute_trade(direction, cst, token, df):
    current_atr = df["atr"].iloc[-1]
    current_price = df["close"].iloc[-1]

    account = get_account_balance(cst, token)
    if not account:
        return

    size = calculate_position_size(current_price, account["balance"])

    # 仅设定止盈，不设止损（stopLevel = None）
    if direction == "BUY":
        initial_tp = current_price+0.09
        #stop_loss=current_price-current_atr*3
    else:
        initial_tp = current_price - current_atr * 2

    order = {
        "epic": EPIC,
        "direction": direction,
        "size": size,
        "orderType": "MARKET",
        "profitLevel": round(initial_tp, 3),
        "stopLevel": None,#round(stop_loss,3),
        "guaranteedStop": False,
        "oco": False         # 没有止损就不启用 OCO
    }

    response = requests.post(
        f"{BASE_URL}positions",
        headers={"CST": cst, "X-SECURITY-TOKEN": token},
        json=order
    )

    if response.status_code == 200:
        print(f"✅ {direction} 下单成功 | 数量: {size} | 价格: {current_price:.3f} | 止盈: {initial_tp:.3f}")
    else:
        print(f"❌ 下单失败: {response.status_code} - {response.text}")



# === 主函数 ===
def mta2(cst, token):
    account = get_account_balance(cst, token)
    if not account:
        return
    print(f"💰 账户余额: {account['balance']}")

    if get_positions(cst, token):
        print("🟡 当前已有持仓，跳过开仓信号")
        return

    df = get_market_data(cst, token, EPIC, RESOLUTION)
    if df is None:
        print("❌ K线数据为空")
        return

    df = calculate_indicators(df)
    signal = generate_signal(df)
    if signal:
        execute_trade(signal, cst, token, df)