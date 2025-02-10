import requests
import pandas as pd
from datetime import datetime
from config import get_market_data,compute_indicators,BASE_URL,EPIC,TRADE_SIZE,TIMEFRAME
import time


MAX_RSI_POSITIONS = 3

# ======== 仓位记录结构 ========
deal_positions = {
    "ema": {
        "buy": None,  # {dealReference, dealId, direction, size, openPrice, timestamp}
        "sell": None
    },
    "macd": {
        "buy": None,
        "sell": None
    },
    "rsi": {
        "buy": [],  # 允许最多MAX_RSI_POSITIONS个多单
        "sell": []  # 允许最多MAX_RSI_POSITIONS个空单
    }
}

# ======== 开仓函数 ========
def place_order(cst, security_token, direction, reason, strategy):
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
        deal_positions[strategy][direction.lower()] = deal_info


def get_current_position(cst, security_token, strategy, direction):
    url = BASE_URL + "positions"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        positions = response.json().get('positions', [])
        
        # 打印出所有仓位的详细信息，方便调试
        print("当前仓位信息:", positions)
        
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


def close_position(cst, security_token, strategy, direction):
    # 获取当前仓位
    position = get_current_position(cst, security_token, strategy, direction)

    if strategy == "rsi":
        # 处理RSI策略的多仓位
        position_key = direction.lower()
        if position:
            # 如果找到仓位，平仓
            deal_id = position.get('dealId')
            if not deal_id:
                print(f"❌ 未找到 {strategy} {direction} 仓位的 dealId")
                return False
            
            url = BASE_URL + f"positions/{deal_id}"
            headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 200:
                print(f"✅ 成功平仓 {strategy} {direction} 仓位，dealId: {deal_id}")
                # 移除仓位（FIFO，最早开的仓位）
                deal_positions["rsi"][position_key].pop(0)  # 从仓位记录中移除
                return True
            else:
                print(f"❌ 平仓失败 {strategy} {direction}: {response.json()}")
                return False
        else:
            print(f"⚠️ 无 {strategy} {direction} 仓位可平")
            return False

    else:
        # 处理普通策略（EMA、MACD）的单仓位
        position_key = direction.lower()
        if position:
            # 如果找到仓位，平仓
            deal_id = position.get('dealId')
            if not deal_id:
                print(f"❌ 未找到 {strategy} {direction} 仓位的 dealId")
                return False
            
            url = BASE_URL + f"positions/{deal_id}"
            headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 200:
                print(f"✅ 成功平仓 {strategy} {direction} 仓位，dealId: {deal_id}")
                deal_positions[strategy][position_key] = None  # 更新仓位记录
                return True
            else:
                print(f"❌ 平仓失败 {strategy} {direction}: {response.text}")
        else:
            print(f"⚠️ 无 {strategy} {direction} 仓位可平")
    return False


# ======== 交易策略函数 ========
def trading_strategy(cst, security_token):
    df = get_market_data(cst, security_token)
    if df is None:
        return
    
    df = compute_indicators(df)
    current = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else current

    # EMA策略
    if current['ema9'] > current['ema21'] and prev['ema9'] <= prev['ema21']:
        if deal_positions["ema"]["sell"]:  # 先平空仓
            close_position(cst, security_token, "ema", "SELL")
        if not deal_positions["ema"]["buy"]:  # 避免重复开仓
            place_order(cst, security_token, "BUY", "EMA金叉", "ema")
            
    elif current['ema9'] < current['ema21'] and prev['ema9'] >= prev['ema21']:
        if deal_positions["ema"]["buy"]:  # 先平多仓
            close_position(cst, security_token, "ema", "BUY")
        if not deal_positions["ema"]["sell"]:  # 避免重复开仓
            place_order(cst, security_token, "SELL", "EMA死叉", "ema")

    # MACD策略
    if current['macd_line'] > current['macd_signal'] and prev['macd_line'] <= prev['macd_signal']:
        # 金叉出现时
        if deal_positions["macd"]["sell"]:  # 先平空仓
            close_position(cst, security_token, "macd", "SELL")
        if not deal_positions["macd"]["buy"]:  # 开多仓
            place_order(cst, security_token, "BUY", "MACD金叉", "macd")
            
    elif current['macd_line'] < current['macd_signal'] and prev['macd_line'] >= prev['macd_signal']:
        # 死叉出现时
        if deal_positions["macd"]["buy"]:  # 先平多仓
            close_position(cst, security_token, "macd", "BUY")
        if not deal_positions["macd"]["sell"]:  # 开空仓
            place_order(cst, security_token, "SELL", "MACD死叉", "macd")

    # RSI策略（优化仓位管理）
    if current['rsi'] < 25:
        # 超卖时平空仓开多仓
        for _ in deal_positions["rsi"]["sell"][:]:  # 遍历副本用于修改原列表
            close_position(cst, security_token, "rsi", "SELL")
        if len(deal_positions["rsi"]["buy"]) < MAX_RSI_POSITIONS:
            place_order(cst, security_token, "BUY", "RSI超卖", "rsi")
            
    elif current['rsi'] > 75:
        # 超买时平多仓开空仓
        for _ in deal_positions["rsi"]["buy"][:]:
            close_position(cst, security_token, "rsi", "BUY")
        if len(deal_positions["rsi"]["sell"]) < MAX_RSI_POSITIONS:
            place_order(cst, security_token, "SELL", "RSI超买", "rsi")