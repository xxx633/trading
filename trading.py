import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# Capital.com API 配置
API_KEY = "fekK4lw5TMmW9PXQ"
CLIENT_IDENTIFIER = "vittoxiong@icloud.com"
PASSWORD = "Password2@123"
BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1/"

# 交易配置
EPIC = "XRPUSD"  # 交易品种
TRADE_SIZE = 100  # 每笔交易大小
TIMEFRAME = "HOUR"  # 时间周期（分钟级别）

# 登录 Capital.com
def login():
    url = BASE_URL + "session"
    headers = {"X-CAP-API-KEY": API_KEY, "Content-Type": "application/json"}
    payload = {"identifier": CLIENT_IDENTIFIER, "password": PASSWORD, "encryptedPassword": False}
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        print("✅ 登录成功！")
        return response.headers["CST"], response.headers["X-SECURITY-TOKEN"]
    else:
        print("❌ 登录失败:", response.json())
        exit()

# 获取市场数据
def get_market_data(cst, security_token):
    url = BASE_URL + f"prices/{EPIC}?resolution={TIMEFRAME}&max=50"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()["prices"]
        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["snapshotTime"])
        df["close"] = df["closePrice"].apply(lambda x: x["bid"])
        return df[["timestamp", "close"]].set_index("timestamp")
    else:
        print("❌ 获取市场数据失败:", response.json())
        return None

# 计算技术指标：EMA, MACD, RSI
def compute_indicators(df):
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()

    df['rsi'] = 100 - (100 / (1 + (df['close'].diff().clip(lower=0).rolling(window=14).mean() / 
                                   df['close'].diff().clip(upper=0).rolling(window=14).mean().abs())))

    df['macd_line'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()

    return df

# 下单函数
def place_order(cst, security_token, direction, reason):
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

    if response.status_code == 200:
        print(f"✅ 成功 {direction} {TRADE_SIZE} {EPIC}，原因: {reason}")
    else:
        print(f"❌ {direction} 失败:", response.json())

# 交易策略
def trading_strategy(cst, security_token):
    positions = []  # 存储所有仓位，允许多个 RSI 订单
    trigger_map = {
        'id1': 'id4',  # RSI多 -> RSI空
        'id2': 'id5',  # EMA多 -> EMA空
        'id3': 'id6',  # MACD多 -> MACD空
        'id4': 'id1',  # RSI空 -> RSI多
        'id5': 'id2',  # EMA空 -> EMA多
        'id6': 'id3'   # MACD空 -> MACD多
    }
    
    # 获取市场数据
    df = get_market_data(cst, security_token)
    if df is None:
        return

    # 计算技术指标
    df = compute_indicators(df)
    
    # 获取最新K线数据
    current = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else current
    
    # 检查交易信号
    signals = []
    if current['rsi'] < 25:
        signals.append(('BUY', 'id1'))  # RSI多
    if current['rsi'] > 75:
        signals.append(('SELL', 'id4'))  # RSI空
    
    if (current['ema9'] > current['ema21']) and (prev['ema9'] <= prev['ema21']):
        signals.append(('BUY', 'id2'))  # EMA金叉
    if (current['ema9'] < current['ema21']) and (prev['ema9'] >= prev['ema21']):
        signals.append(('SELL', 'id5'))  # EMA死叉
    
    if (current['macd_line'] > current['macd_signal']) and (prev['macd_line'] <= prev['macd_signal']):
        signals.append(('BUY', 'id3'))  # MACD金叉
    if (current['macd_line'] < current['macd_signal']) and (prev['macd_line'] >= prev['macd_signal']):
        signals.append(('SELL', 'id6'))  # MACD死叉
    
    # 处理开仓信号
    for signal in signals:
        direction, trigger_id = signal
        reason = "RSI" if "id1" in trigger_id or "id4" in trigger_id else \
                 "EMA" if "id2" in trigger_id or "id5" in trigger_id else "MACD"
        
        if trigger_id == 'id1':  # RSI多
            if len([p for p in positions if p['trigger_id'] == 'id1']) < 3:
                place_order(cst, security_token, direction, reason)
                positions.append({'trigger_id': trigger_id, 'direction': direction, 'stop_loss_id': trigger_map[trigger_id]})
        elif trigger_id != 'id1':
            if not any(p['trigger_id'] == trigger_id for p in positions):
                place_order(cst, security_token, direction, reason)
                positions.append({'trigger_id': trigger_id, 'direction': direction, 'stop_loss_id': trigger_map[trigger_id]})

    # 处理平仓信号
    for position in list(positions):
        trigger_id = position['trigger_id']
        exit_trigger_id = position['stop_loss_id']
        for signal in signals:
            direction, signal_trigger_id = signal
            if signal_trigger_id == exit_trigger_id:
                reason = "RSI" if "id1" in trigger_id or "id4" in trigger_id else \
                         "EMA" if "id2" in trigger_id or "id5" in trigger_id else "MACD"

                place_order(cst, security_token, 'SELL' if position['direction'] == 'BUY' else 'BUY', reason)
                positions.remove(position)
                
                new_direction = 'SELL' if position['direction'] == 'BUY' else 'BUY'
                place_order(cst, security_token, new_direction, reason)
                positions.append({'trigger_id': trigger_map[trigger_id], 'direction': new_direction, 'stop_loss_id': trigger_map[trigger_map[trigger_id]]})
                
                break
