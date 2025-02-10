import requests
import pandas as pd
import time 

# ======== 配置部分 ========
API_KEY = "fekK4lw5TMmW9PXQ"
CLIENT_IDENTIFIER = "vittoxiong@icloud.com"
PASSWORD = "Password2@123"
BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1/"

EPIC = "XRPUSD"
TRADE_SIZE = 100
TIMEFRAME = "HOUR"

# ======== 登录函数 ========
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

# ======== 获取市场数据 ========
def get_market_data(cst, security_token):
    url = BASE_URL + f"prices/{EPIC}?resolution={TIMEFRAME}&max=50"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    
    response = requests.get(url, headers=headers)
    
    # 打印响应状态码和内容，用于调试
    #print("Status Code:", response.status_code)
    #print("Response Text:", response.text)
    
    if response.status_code == 200:
        try:
            data = response.json()["prices"]
            df = pd.DataFrame(data)
            df["timestamp"] = pd.to_datetime(df["snapshotTime"])
            df["close"] = df["closePrice"].apply(lambda x: x["bid"])
            return df[["timestamp", "close"]].set_index("timestamp")
        except ValueError as e:
            print("❌ 解析 JSON 失败:", e)
            return None
    else:
        print("❌ 获取市场数据失败:", response.status_code)
        return None
    

# ======== 计算技术指标 ========
def compute_indicators(df):
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + (df['close'].diff().clip(lower=0).rolling(window=14).mean() / 
                                   df['close'].diff().clip(upper=0).rolling(window=14).mean().abs())))
    df['macd_line'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
    return df
