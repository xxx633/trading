import requests
import pandas as pd
import json
import sys
import os
import numpy as np
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import *


EPIC="ETHUSD"
TRADE_SIZE = 0.01
LOWER = "MINUTE"
HIGHER = "MINUTE_5"

# 策略参数
FAST_EMA = 9
SLOW_EMA = 21
ATR_PERIOD = 14
ATR_MULTIPLIER = 2.0  # 增加 ATR 倍数，避免过紧止损
TRAILING_STOP_PERC = 2.0 / 100

# 全局变量记录买入次数和总盈利
buy_count = 0
total_profit = 0.0
trailing_stop_price = None

# 计算 EMA 和 ATR 指标
def calculate_indicators(df):
    df["fast_ema"] = df["close"].ewm(span=FAST_EMA, adjust=False).mean()
    df["slow_ema"] = df["close"].ewm(span=SLOW_EMA, adjust=False).mean()
    
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.abs(df['high'] - df['prev_close']),
        np.abs(df['low'] - df['prev_close'])
    )
    # 计算 ATR
    df['atr'] = df['tr'].rolling(ATR_PERIOD).mean() * ATR_MULTIPLIER
    df.drop(columns=['prev_close', 'tr'], inplace=True)
    return df

# 动态止盈策略：计算止盈价格
def update_trailing_stop(cst, security_token):
    global trailing_stop_price
    position = get_position(cst, security_token)

    if not position:
        trailing_stop_price = None  # 无持仓时重置
        return None

    if position:
        # 获取当前市场价格
        current_price = get_market_data(cst, security_token, EPIC, LOWER)["close"].iloc[-1]
        
        # 计算当前止盈价格
        if position.get("direction") == "BUY":
            # 对于买单，止盈价格需要随着上涨调整
            if trailing_stop_price is None:
                trailing_stop_price = current_price * (1 - TRAILING_STOP_PERC)  # 初始止盈价格
            else:
                # 只有当前价格高于上一个止盈价格时才更新
                if current_price > trailing_stop_price / (1 - TRAILING_STOP_PERC):
                    trailing_stop_price = current_price * (1 - TRAILING_STOP_PERC)

        elif position.get("direction") == "SELL":
            # 对于卖单，止盈价格需要随着下跌调整
            if trailing_stop_price is None:
                trailing_stop_price = current_price * (1 + TRAILING_STOP_PERC)  # 初始止盈价格
            else:
                # 只有当前价格低于上一个止盈价格时才更新
                if current_price < trailing_stop_price / (1 + TRAILING_STOP_PERC):
                    trailing_stop_price = current_price * (1 + TRAILING_STOP_PERC)
        
        print(f"当前止盈价格: {trailing_stop_price}")
    
    return trailing_stop_price

# 获取当前持仓
def get_position(cst, security_token):
    url = BASE_URL + "positions"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        positions = response.json().get('positions', [])
        for pos in positions:
            if pos.get("market", {}).get("epic") == EPIC:
                return pos
    else:
        print("❌ 获取持仓信息失败:", response.json())
    return None

# 查询订单状态
def get_order_status(deal_reference, cst, security_token):
    url = BASE_URL + f"confirms/{deal_reference}"
    headers = {
        "CST": cst,
        "X-SECURITY-TOKEN": security_token,
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        order_details = response.json()
        #print("✅ 订单详情:", json.dumps(order_details, indent=4, ensure_ascii=False))
        return order_details
    else:
        print("❌ 获取订单详情失败:", response.json())
        return None

# 开仓 待接入payload profitdistance stopdistance
def open_position(direction, cst, security_token):
    global buy_count
    url = BASE_URL + "positions"
    payload = {"epic": EPIC, "direction": direction, "size": TRADE_SIZE, "orderType": "MARKET"}
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        position = response.json()
        buy_count += 1

        # 如果返回的响应中有 dealReference, 查询交易详情
        if "dealReference" in position:
            order_details = get_order_status(position["dealReference"], cst, security_token)
            
            if order_details:
                # 打印开仓价格
                level = order_details.get("level")
                if level:
                    print(f"✅ 成功开仓: {direction} ，开盘价格: {level:.2f}")
                    print(f"📊 开仓总数: {buy_count} 次")
                else:
                    print("❌ 未找到开仓价格.")
        return position
    else:
        print("❌ 开仓失败:", response.json())
    return None

# 平仓
def close_position(cst, security_token):
    global total_profit, trailing_stop_price
    position = get_position(cst, security_token)
    
    if position:
        current_price = get_market_data(cst, security_token,EPIC,LOWER)["close"].iloc[-1]
        
        # 判断是否触及止盈价格
        if position.get("direction") == "BUY" and current_price <= trailing_stop_price:
            print(f"触及止盈价格 {trailing_stop_price}, 开始平仓!")
            trade_profit = (current_price - position["openPrice"])
            total_profit += trade_profit
            url = f"{BASE_URL}/positions/{position['dealId']}"
            headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 200:
                print(f"✅ 平仓成功！平仓价格: {current_price}")
                trailing_stop_price = None  # 重置止盈价格
                print(f"💰 本次交易盈利: {trade_profit}")
                print(f"💵 总体盈利: {total_profit}")
            else:
                print("❌ 平仓失败:", response.json())
        elif position.get("direction") == "SELL" and current_price >= trailing_stop_price:
            print(f"触及止盈价格 {trailing_stop_price}, 开始平仓!")
            trade_profit = (position["openPrice"] - current_price)
            total_profit += trade_profit
            url = f"{BASE_URL}/positions/{position['dealId']}"
            headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 200:
                print(f"✅ 平仓成功！平仓价格: {current_price}")
                print(f"💰 本次交易盈利: {trade_profit}")
                print(f"💵 总体盈利: {total_profit}")
            else:
                print("❌ 平仓失败:", response.json())
    return None

