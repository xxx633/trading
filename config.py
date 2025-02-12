import requests
import pandas as pd
import time 

# ======== 配置部分 ========
API_KEY = "fekK4lw5TMmW9PXQ"
CLIENT_IDENTIFIER = "vittoxiong@icloud.com"
PASSWORD = "Password2@123"
BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1/"

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
def get_market_data(cst, security_token,epic,resolution):
    url = BASE_URL + f"prices/{epic}?resolution={resolution}&max=50"
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
            df["high"] = df["highPrice"].apply(lambda x: x["bid"])
            df["low"] = df["lowPrice"].apply(lambda x: x["bid"])
            
            # 只保留时间戳、收盘价、最高价和最低价
            return df[["timestamp", "close", "high", "low"]].set_index("timestamp")
        except ValueError as e:
            print("❌ 解析 JSON 失败:", e)
            return None
    else:
        print("❌ 获取市场数据失败:", response.status_code)
        return None  
    

def get_account_balance(cst, token):
    """获取账户余额（适配Capital.com）"""
    url = f"{BASE_URL}accounts"
    response = requests.get(url, headers={"CST": cst, "X-SECURITY-TOKEN": token})
    if response.status_code == 200:
        accounts = response.json()
        if accounts:
            return {
                "balance": float(accounts[0]["balance"]),
                "currency": accounts[0]["currency"]
            }
    print("❌ 获取账户余额失败:", response.text)
    return None


