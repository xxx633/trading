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
EPIC = "XRPEUR"
RESOLUTION = "HOUR"
ATR_PERIOD = 14
STOP_MULTIPLIER = 2

# === 技术指标计算 ===
def calculate_indicators(df):
    # EMA50
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

    # MACD
    df["ema12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema26"] = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = df["ema12"] - df["ema26"]
    df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # ATR
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(df['high'] - df['low'],
                          np.abs(df['high'] - df['prev_close']),
                          np.abs(df['low'] - df['prev_close']))
    df['atr'] = df['tr'].rolling(ATR_PERIOD).mean()

    # ADX (14)
    df['up_move'] = df['high'].diff()
    df['down_move'] = -df['low'].diff()
    df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    df['tr14'] = df['tr'].rolling(14).sum()
    df['plus_di'] = 100 * (df['plus_dm'].rolling(14).sum() / df['tr14'])
    df['minus_di'] = 100 * (df['minus_dm'].rolling(14).sum() / df['tr14'])
    df['dx'] = 100 * np.abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['adx'] = df['dx'].rolling(14).mean()
    df.drop(columns=['up_move','down_move','plus_dm','minus_dm','tr14','plus_di','minus_di','dx'], inplace=True)
    
    return df

# === 仓位计算 ===
def calculate_position_size(current_price, account_balance, atr, stop_multiplier=1.5, risk_ratio=0.02, leverage=2):
    risk_amount = account_balance * risk_ratio
    stop_distance = atr * stop_multiplier
    if stop_distance == 0:
        stop_distance = 0.01
    size = risk_amount / stop_distance
    return max(round(size, 2), 1)

# === 信号生成 ===
def generate_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # 趋势过滤
    if last["adx"] < 25:
        return None

    # 可选成交量过滤
    # avg_vol = df["volume"].iloc[-20:].mean()
    # if last["volume"] < avg_vol:
    #     return None

    long_cond = (
        last["close"] > last["ema50"] and
        last["rsi"] >= 50 and
        prev["macd"] <= prev["signal"] and
        last["macd"] > last["signal"]
    )

    short_cond = (
        last["close"] < last["ema50"] and
        last["rsi"] <= 50 and
        prev["macd"] >= prev["signal"] and
        last["macd"] < last["signal"]
    )

    if long_cond:
        return "BUY"
    elif short_cond:
        return "SELL"
    return None

# === 执行下单 ===
def execute_trade(direction, cst, token, df):
    current_atr = df["atr"].iloc[-1]
    current_price = df["close"].iloc[-1]

    account = get_account_balance(cst, token)
    if not account:
        return

    size = calculate_position_size(current_price, account["balance"], current_atr)

    if direction == "BUY":
        stop_loss = current_price - current_atr * STOP_MULTIPLIER
        initial_tp = current_price + current_atr * STOP_MULTIPLIER * 2
    else:
        stop_loss = current_price + current_atr * STOP_MULTIPLIER
        initial_tp = current_price - current_atr * STOP_MULTIPLIER * 2

    order = {
        "epic": EPIC,
        "direction": direction,
        "size": size,
        "orderType": "MARKET",
        "stopLevel": round(stop_loss,3),
        "profitLevel": round(initial_tp,3),
        "guaranteedStop": False,
        "oco": True
    }

    response = requests.post(f"{BASE_URL}positions", headers={"CST": cst, "X-SECURITY-TOKEN": token}, json=order)
    if response.status_code == 200:
        print(f"✅ {direction} 下单成功 | 数量: {size} | 价格: {current_price:.2f} | 止损: {stop_loss:.2f} | 止盈: {initial_tp:.2f}")
    else:
        print(f"❌ 下单失败: {response.status_code} - {response.text}")

# === 获取持仓 ===
def get_positions(cst, token):
    url = BASE_URL + "positions"
    headers = {"CST": cst, "X-SECURITY-TOKEN": token, "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('positions', [])
    else:
        print(f"❌ 获取持仓失败: {response.text}")
        return []

# === 平仓 ===
def close_position(deal_id, cst, token):
    url = BASE_URL + f"positions/{deal_id}"
    headers = {"CST": cst, "X-SECURITY-TOKEN": token}
    response = requests.delete(url, headers=headers)
    if response.status_code == 200:
        print(f"🔵 成功平仓 dealId: {deal_id}")
    else:
        print(f"❌ 平仓失败 dealId {deal_id}: {response.text}")

# === 动态止损 / 检查平仓 ===
def check_exit_conditions(cst, token, df):
    positions = get_positions(cst, token)
    if not positions:
        return

    current_price = df["close"].iloc[-1]
    current_atr = df["atr"].iloc[-1]

    for pos in positions:
        direction = pos["position"]["direction"]
        deal_id = pos["position"]["dealId"]
        entry_price = pos["position"]["level"]

        if direction == "BUY":
            trailing_stop = max(entry_price, current_price - current_atr * STOP_MULTIPLIER)
            if current_price <= trailing_stop:
                close_position(deal_id, cst, token)
        elif direction == "SELL":
            trailing_stop = min(entry_price, current_price + current_atr * STOP_MULTIPLIER)
            if current_price >= trailing_stop:
                close_position(deal_id, cst, token)

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