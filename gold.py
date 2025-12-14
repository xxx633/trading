import requests
import pandas as pd
import numpy as np
import sys
import os
import time
from datetime import datetime,timezone
# 添加项目根目录到系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import *

EPIC = "GOLD"        # 交易品种
RESOLUTION = "MINUTE"    # 交易周期 30_MINUTE HOUR
L=20 #Leverage
a=0.5 #Margin call
forex=1.17

position= {
    'p1':None,
    'p2':None,
    'p3':None
}

pivot = None
last_pivot_date=None
pivot_update=False

#region order
def get_pending_orders(cst, security_token):
    url = BASE_URL + "orders"
    headers = {
        "CST": cst,
        "X-SECURITY-TOKEN": security_token
    }
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        return []

    return r.json().get("orders", [])

def cancel_order(cst, security_token, order_id):
    url = BASE_URL + f"orders/{order_id}"
    headers = {
        "CST": cst,
        "X-SECURITY-TOKEN": security_token
    }

    r = requests.delete(url, headers=headers)

    if r.status_code == 200:
        print(f"✅ Order {order_id} cancelled")
        return True
    else:
        print("❌ Cancel failed:", r.text)
        return False

def cancel_all_orders(cst, token):
    orders = get_pending_orders(cst, token)
    for o in orders:
        cancel_order(cst, token, o["orderId"])

#endregion

def calculate_position_size(current_price,balance,level):
    capital=balance*forex*10

    size=(capital*level)/current_price

    return round(size,2)

def execute_trade(cst, token,buyat,tp,level):
    account = get_account_balance(cst, token)
    if not account:
        return
    
    df=get_market_data(cst,token,EPIC,"MINUTE")
    current_price=df.iloc[-1]

    size = calculate_position_size(current_price, account["balance"],level)

    if(buyat>current_price):
        type="STOP"
    else:
        type="LIMIT"

    order = {
        "epic": EPIC,
        "direction": "BUY",
        "size": size,
        "orderType": type,
        "level":buyat,
        "profitLevel": tp,
        "stopLevel": None,
        "guaranteedStop": False,
        "oco": False         # 没有止损就不启用 OCO
    }

    response = requests.post(
        f"{BASE_URL}positions",
        headers={"CST": cst, "X-SECURITY-TOKEN": token},
        json=order
    )

    if response.status_code == 200:
        print(f"✅ 挂单成功 | 数量: {size} | 价格: {current_price:.0f} | 止盈: {tp:.0f}")
    else:
        print(f"❌ 挂单失败: {response.status_code} - {response.text}")

def update_pivots(cst,token,now):
    global pivots, last_pivot_date,pivot_update

    today = now.date()

    # 第一次启动 or 新的一天
    if pivots is None or last_pivot_date != today:
        df_day = get_market_data(cst, token,"DAY")
        
        # 用“前一日”算 pivot（不是最后一根）
        prev = df_day.iloc[-2]

        pivots = {
            "PP": (prev.high + prev.low + 2 * prev.close) / 4,
            "R1": None,
            "S1": None,
            "R2": None,
            "S2": None
        }

        pivots["R1"] = 2 * pivots["PP"] - prev.low
        pivots["S1"] = 2 * pivots["PP"] - prev.high
        pivots["R2"] = pivots["PP"] + (prev.high - prev.low)
        pivots["S2"] = pivots["PP"] - (prev.high - prev.low)

        last_pivot_date = today
        pivot_update=True
        print("✅ Pivot updated:", pivots)
    else:
        pivot_update=False   

def gold(cst,token):
    #每日更新pivots
    now=datetime.now(timezone.utc)
    update_pivots(cst,token,now)

    if pivot_update:
        cancel_all_orders(cst,token)
    
    # where are at position
    #Check Position
    if(position['p1'] is None):
        execute_trade(cst,token,pivot['PP'],pivot['R1'],level=0.5)

    if(position['p2'] is None):
        execute_trade(cst,token,pivot['S1'],pivot['R1'],level=0.3)

    if(position['p3'] is None):
        execute_trade(cst,token,pivot['S2'],pivot['R2'],level=0.2)












