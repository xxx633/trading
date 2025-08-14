import requests
import pandas as pd
import numpy as np
from datetime import datetime
from config import *

# === 配置 ===
EPIC = "XRPEUR"
RESOLUTION = "MINUTE_30"
GRID_SIZE = 0.002  # 网格间距（单位: 欧元）
GRID_LEVELS = 10   # 网格层数（上下各5格）
REFRESH_INTERVAL = 48  # 每多少根K线重新计算网格中心

# 全局变量
grid_center_price = None
grid_prices = []

def get_positions(cst, security_token):
    url = BASE_URL + "positions"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get('positions', [])
    else:
        print(f"❌ 获取持仓信息失败: {response.text}")
        return []

def calculate_grid_levels(center_price):
    """根据中心价格计算上下的网格价格"""
    return [round(center_price + (i - GRID_LEVELS//2) * GRID_SIZE, 4) for i in range(GRID_LEVELS)]

def update_grid(cst, token, df):
    """根据行情更新网格中心和价格列表"""
    global grid_center_price, grid_prices
    grid_center_price = df["close"].iloc[-1]
    grid_prices = calculate_grid_levels(grid_center_price)
    print(f"📐 重新设定网格中心价 {grid_center_price:.4f}，价格区间: {min(grid_prices):.4f} ~ {max(grid_prices):.4f}")

def place_order(cst, token, direction, price):
    """下单（限价）"""
    balance=get_account_balance(cst,token)
    size=balance/10
    order = {
        "epic": EPIC,
        "direction": direction,
        "size": size,
        "orderType": "LIMIT",
        "level": round(price, 4),
        "guaranteedStop": False
    }
    response = requests.post(
        f"{BASE_URL}positions",
        headers={"CST": cst, "X-SECURITY-TOKEN": token},
        json=order
    )
    if response.status_code == 200:
        print(f"✅ 挂单 {direction} @ {price}")
    else:
        print(f"❌ 挂单失败: {response.text}")

def run_grid_logic(cst, token, df):
    """核心网格逻辑"""
    global grid_prices
    current_price = df["close"].iloc[-1]

    # 检查现有持仓
    positions = get_positions(cst, token)
    position_prices = [float(p["position"]["level"]) for p in positions]

    # 遍历网格价格，挂单
    for price in grid_prices:
        if price < current_price and price not in position_prices:
            # 下买单（低买）
            place_order(cst, token, "BUY", price)
        elif price > current_price and price not in position_prices:
            # 下卖单（高卖）
            place_order(cst, token, "SELL", price)

def gpt(cst, token):
    """主策略函数：获取数据 -> 更新网格 -> 挂单"""
    df = get_market_data(cst, token, EPIC, RESOLUTION)
    if df is None or df.empty:
        print("❌ 无法获取市场数据")
        return

    # 每隔 REFRESH_INTERVAL 根K线更新网格
    if len(df) % REFRESH_INTERVAL == 0 or grid_center_price is None:
        update_grid(cst, token, df)

    run_grid_logic(cst, token, df)