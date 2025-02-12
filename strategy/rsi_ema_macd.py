from datetime import datetime
import sys
import os
import time
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import *

MAX_RSI_POSITIONS = 3
EPIC="XRPUSD"
TRADE_SIZE = 100
TIMEFRAME = "HOUR"

# ======== 仓位记录结构 ========
deal_positions = {
    "ema": {
        "buy": None,   # {dealReference, dealId, direction, size, openPrice, timestamp}
        "sell": None
    },
    "macd": {
        "buy": None,
        "sell": None
    },
    "rsi": {
        "buy": [],     # 允许最多 MAX_RSI_POSITIONS 个多单
        "sell": []     # 允许最多 MAX_RSI_POSITIONS 个空单
    },
    "bb": {
        "buy": None,   
        "sell": None  
    }
}

# ======== 计算技术指标 ========
def compute_indicators(df):
    # EMA 指标
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    #df['ema50'] = df['close'].ewm(span=50, adjust=False).mean() 
    # RSI 指标（14周期）
    df['rsi'] = 100 - (100 / (1 + (df['close'].diff().clip(lower=0)
                                  .rolling(window=14).mean() /
                                  df['close'].diff().clip(upper=0)
                                  .rolling(window=14).mean().abs()
                                  .clip(lower=1e-8))))  # 加上防止除0的小值
    
    # MACD 指标
    df['macd_line'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
    
    # 布林带指标（20周期，2倍标准差）
    df['bb_mid'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']
    
    return df

# ======== 开仓函数 ========
def open_position(cst, security_token, direction, reason, strategy):
    url = BASE_URL + "positions"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    payload = {
        "epic": EPIC,
        "direction": direction,
        "size": TRADE_SIZE,
        "orderType": "MARKET",
        "timeInForce": "FILL_OR_KILL"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    # 打印响应的原始内容，帮助调试
    print(f"API 响应: {response.status_code} - {response.text}")
    
    if response.status_code == 200:
        try:
            # 尝试解析响应 JSON
            deal_reference = response.json().get("dealReference")
            if deal_reference:
                time.sleep(1)  # 等待订单确认
                deal_info = confirm_order(cst, security_token, deal_reference)
                if deal_info:
                    record_position(strategy, direction, deal_info)
                    print(f"✅ 成功 {direction} {TRADE_SIZE} {EPIC}，原因: {reason}")
        except ValueError:
            print("❌ 响应内容不是有效的 JSON:", response.text)
    else:
        print(f"❌ {direction} 失败: 状态码 {response.status_code}，响应内容: {response.text}")

# ======== 订单确认并记录仓位 ========
def confirm_order(cst, security_token, deal_reference):
    url = BASE_URL + f"confirms/{deal_reference}"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        deal_info = response.json()
        return {
            "dealReference": deal_reference,
            "dealId": deal_info.get("dealId"),
            "direction": deal_info.get("direction"),
            "size": deal_info.get("size"),
            "openPrice": deal_info.get("level"),
            "timestamp": datetime.now().isoformat()
        }
    return None

# ======== 记录仓位信息 ========
def record_position(strategy, direction, deal_info):
    if strategy == "rsi":
        if direction == "BUY":
            if len(deal_positions["rsi"]["buy"]) < MAX_RSI_POSITIONS:
                deal_positions["rsi"]["buy"].append(deal_info)
        else:
            if len(deal_positions["rsi"]["sell"]) < MAX_RSI_POSITIONS:
                deal_positions["rsi"]["sell"].append(deal_info)
    else:
        # ema、macd、bb 均为单仓位
        deal_positions[strategy][direction.lower()] = deal_info

# ======== 平仓函数 ========
def close_position(cst, security_token, strategy, direction):
    # 获取当前仓位
    position = get_current_position(cst, security_token, strategy, direction)

    if strategy == "rsi":
        # 处理 RSI 策略的多仓位（列表记录）
        position_key = direction.lower()
        if position:
            deal_id = position.get('dealId')
            if not deal_id:
                print(f"❌ 未找到 {strategy} {direction} 仓位的 dealId")
                return False
            
            url = BASE_URL + f"positions/{deal_id}"
            headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 200:
                print(f"✅ 成功平仓 {strategy} {direction} 仓位，dealId: {deal_id}")
                # FIFO，移除最早的仓位
                deal_positions["rsi"][position_key].pop(0)
                return True
            else:
                print(f"❌ 平仓失败 {strategy} {direction}: {response.json()}")
                return False
        else:
            print(f"⚠️ 无 {strategy} {direction} 仓位可平")
            return False

    else:
        # 处理 ema、macd、bb 等单仓位策略
        position_key = direction.lower()
        if position:
            deal_id = position.get('dealId')
            if not deal_id:
                print(f"❌ 未找到 {strategy} {direction} 仓位的 dealId")
                return False
            
            url = BASE_URL + f"positions/{deal_id}"
            headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 200:
                print(f"✅ 成功平仓 {strategy} {direction} 仓位，dealId: {deal_id}")
                deal_positions[strategy][position_key] = None
                return True
            else:
                print(f"❌ 平仓失败 {strategy} {direction}: {response.text}")
        else:
            print(f"⚠️ 无 {strategy} {direction} 仓位可平")
    return False

# ======== 获取仓位信息 ========
def get_current_position(cst, security_token, strategy, direction):
    url = BASE_URL + "positions"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        positions = response.json().get('positions', [])
        
        # 遍历当前所有仓位，查找与 EPIC 及方向匹配的
        for item in positions:
            pos = item.get('position', {})
            market = item.get('market', {})
            if market.get('epic') == EPIC and pos.get('direction') == direction:
                return {
                    "dealId": pos.get('dealId'),
                    "direction": pos.get('direction'),
                    "size": pos.get('size'),
                    "openPrice": pos.get('level'),
                    "timestamp": pos.get('createdDate')
                }
    else:
        print(f"❌ 获取持仓信息失败:", response.json())
    return None


    
    