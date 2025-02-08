import requests
import pandas as pd
import time
from flask import Flask, jsonify

app = Flask(__name__)

# =============== 1. 配置 API ===============
API_KEY = "fekK4lw5TMmW9PXQ"
CLIENT_IDENTIFIER = "vittoxiong@icloud.com"
PASSWORD = "Password2@123"

BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1/"  # 模拟账户
# BASE_URL = "https://api-capital.backend-capital.com/api/v1/"  # 真实账户

EPIC = "XRPUSD"  # 交易标的：Ripple/USD
TRADE_SIZE = 100  # 每次交易的 XRP 数量
TIMEFRAME = "MINUTE"  # 1 分钟 K 线

# =============== 2. 登录 ===============
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

# =============== 3. 获取市场数据 ===============
def get_market_data(cst, security_token):
    url = BASE_URL + f"prices/{EPIC}?resolution={TIMEFRAME}&max=50"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()["prices"]
        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["snapshotTime"])
        df["close"] = df["closePrice"].apply(lambda x: x["bid"])  # 取收盘价
        return df[["timestamp", "close"]].set_index("timestamp")
    else:
        print("❌ 获取市场数据失败:", response.json())
        return None

# =============== 4. 计算 EMA ===============
def calculate_ema(df, period):
    return df["close"].ewm(span=period, adjust=False).mean()

# =============== 5. 交易 ===============
def place_order(cst, security_token, direction):
    url = BASE_URL + "positions"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    
    payload = {
        "epic": EPIC,
        "direction": direction,  # "BUY" 或 "SELL"
        "size": TRADE_SIZE,
        "orderType": "MARKET",
        "timeInForce": "FILL_OR_KILL"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    print(f"📤 交易请求: {direction} 100 XRP/USD")
    print("📩 API 响应:", response.json())  # 打印 API 响应，方便调试

    if response.status_code == 200:
        print(f"✅ 成功 {direction} 100 XRP/USD")
    else:
        print(f"❌ {direction} 失败:", response.json())  

# =============== 6. 交易策略 ===============
def trading_strategy(cst, security_token):
    df = get_market_data(cst, security_token)  # 获取 1 分钟 K 线数据
    if df is None or len(df) < 21:
        print("⚠️ 数据不足，等待更多K线")
        return
    
    df["EMA9"] = calculate_ema(df, 9)
    df["EMA20"] = calculate_ema(df, 20)
    
    last_row = df.iloc[-1]  # 取最新一根 K 线
    prev_row = df.iloc[-2]  # 取上一根 K 线
    
    print(f"🔍 当前 EMA9: {last_row['EMA9']:.4f}, EMA20: {last_row['EMA20']:.4f}")

    if prev_row["EMA9"] < prev_row["EMA20"] and last_row["EMA9"] > last_row["EMA20"]:
        print("💹 交易信号：买入")
        place_order(cst, security_token, "BUY")

    elif prev_row["EMA9"] > prev_row["EMA20"] and last_row["EMA9"] < last_row["EMA20"]:
        print("📉 交易信号：卖出")
        place_order(cst, security_token, "SELL")

    else:
        print("📉 没有交易信号，继续等待...")

# =============== 7. 健康检查路由 ===============
@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

# =============== 8. 启动交易的路由 ===============
@app.route('/start-trading', methods=['GET'])
def start_trading():
    try:
        cst, security_token = login()
        while True:
            print("\n📊 检查交易信号...")
            trading_strategy(cst, security_token)
            print("⏳ 等待 1 分钟...")
            time.sleep(60)
    except KeyboardInterrupt:
        return jsonify({"message": "交易终止，退出程序"}), 200
    return jsonify({"message": "交易开始"}), 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)