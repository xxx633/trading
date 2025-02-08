from flask import Flask
import requests
import pandas as pd
import time
from threading import Thread

# 初始化 Flask 应用
app = Flask(__name__)

# ==================== 交易相关代码 ====================
API_KEY = "fekK4lw5TMmW9PXQ"
CLIENT_IDENTIFIER = "vittoxiong@icloud.com"
PASSWORD = "Password2@123"
BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1/"
EPIC = "XRPUSD"
TRADE_SIZE = 100
TIMEFRAME = "MINUTE"

# 1️⃣ *登录 API*
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

# 2️⃣ *获取市场数据*
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

# 3️⃣ *计算 EMA*
def calculate_ema(df, period):
    return df["close"].ewm(span=period, adjust=False).mean()

# 4️⃣ *执行交易*
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

# 5️⃣ *交易策略*
def trading_strategy(cst, security_token):
    df = get_market_data(cst, security_token)  # 获取 1 分钟 K 线数据
    if df is None or len(df) < 21:
        print("⚠️ 数据不足，等待更多K线")
        return
    
    df["EMA9"] = calculate_ema(df, 9)
    df["EMA20"] = calculate_ema(df, 20)
    
    last_row = df.iloc[-1]  # 取最新一根 K 线
    prev_row = df.iloc[-2]  # 取上一根 K 线
    
    print(f"🔍 当前 EMA9: {last_row['EMA9']:.5f}, EMA20: {last_row['EMA20']:.5f}")

    if prev_row["EMA9"] < prev_row["EMA20"] and last_row["EMA9"] > last_row["EMA20"]:
        print("💹 交易信号：买入")
        place_order(cst, security_token, "BUY")

    elif prev_row["EMA9"] > prev_row["EMA20"] and last_row["EMA9"] < last_row["EMA20"]:
        print("📉 交易信号：卖出")
        place_order(cst, security_token, "SELL")

    else:
        print("📉 没有交易信号，继续等待...")

# ==================== Koyeb 健康检查 ====================
@app.route('/health', methods=['GET'])
def health_check():
    return "Healthy", 200  # Koyeb 访问这个端口，返回 200 OK

# ==================== 运行交易 ====================
if __name__ == "__main__":
    # 启动 Flask 服务器（健康检查）
    def run_flask():
        app.run(host="0.0.0.0", port=8000)
    
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    try:
        # 启动交易程序
        cst, security_token = login()
        while True:
            print("\n📊 检查交易信号...")
            trading_strategy(cst, security_token)
            print("⏳ 等待 1 分钟...")
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 交易终止，退出程序")