import requests
import pandas as pd
import time

API_KEY = "fekK4lw5TMmW9PXQ"
CLIENT_IDENTIFIER = "vittoxiong@icloud.com"
PASSWORD = "Password2@123"
BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1/"
EPIC = "XRPUSD"
TRADE_SIZE = 100
TIMEFRAME = "MINUTE"

def login():
    try:
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
    except KeyboardInterrupt:
        print("\n🛑 交易终止，退出登录")
        exit()

def get_market_data(cst, security_token):
    try:
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
    except KeyboardInterrupt:
        print("\n🛑 交易终止，退出市场数据获取")
        exit()

def calculate_ema(df, period):
    return df["close"].ewm(span=period, adjust=False).mean()

def place_order(cst, security_token, direction):
    try:
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
        print(f"📤 交易请求: {direction} 100 XRP/USD")
        print("📩 API 响应:", response.json())

        if response.status_code == 200:
            print(f"✅ 成功 {direction} 100 XRP/USD")
        else:
            print(f"❌ {direction} 失败:", response.json())  
    except KeyboardInterrupt:
        print("\n🛑 交易终止，取消下单")
        exit()

def trading_strategy(cst, security_token):
    try:
        df = get_market_data(cst, security_token)
        if df is None or len(df) < 21:
            print("⚠️ 数据不足，等待更多K线")
            return
        
        df["EMA9"] = calculate_ema(df, 9)
        df["EMA20"] = calculate_ema(df, 20)
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        print(f"🔍 当前 EMA9: {last_row['EMA9']:.4f}, EMA20: {last_row['EMA20']:.4f}")

        if prev_row["EMA9"] < prev_row["EMA20"] and last_row["EMA9"] > last_row["EMA20"]:
            print("💹 交易信号：买入")
            place_order(cst, security_token, "BUY")

        elif prev_row["EMA9"] > prev_row["EMA20"] and last_row["EMA9"] < last_row["EMA20"]:
            print("📉 交易信号：卖出")
            place_order(cst, security_token, "SELL")

        else:
            print("📉 没有交易信号，继续等待...")
    except KeyboardInterrupt:
        print("\n🛑 交易策略终止")
        exit()