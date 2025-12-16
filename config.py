import requests
import pandas as pd
import time 
import numpy as np
import os
import json
# ======== 配置部分 ========
API_KEY = os.getenv('API')
CLIENT_IDENTIFIER =os.getenv('EMAIL')
PASSWORD="Password2@123"
BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1/"


class LoginError(Exception):
    """登录失败异常"""
    pass

def login():
    url = BASE_URL + "session"
    headers = {"X-CAP-API-KEY": API_KEY, "Content-Type": "application/json"}
    payload = {"identifier": CLIENT_IDENTIFIER, "password": PASSWORD, "encryptedPassword": False}
    
    for attempt in range(1, 4):
        try:
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                print("✅ 登录成功！")
                return response.headers["CST"], response.headers["X-SECURITY-TOKEN"]
            else:
                print(f"❌ 登录失败: {response.json()}")
        
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求错误: {e}")

        # 如果不是最后一次尝试，打印重试信息
        if attempt < 3:
            print(f"🔄 正在重试... {attempt}/3")
            time.sleep(2)
        else:
            # 达到最大重试次数，抛出异常而不是 exit()
            raise LoginError("⚠️ 达到最大重试次数，登录失败")



"""
# ======== 登录函数 ========
def old_login():
    url = BASE_URL + "session"
    headers = {"X-CAP-API-KEY": API_KEY, "Content-Type": "application/json"}
    payload = {"identifier": CLIENT_IDENTIFIER, "password": PASSWORD, "encryptedPassword": False}
    
    ///
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        print("✅ 登录成功！")
        return response.headers["CST"], response.headers["X-SECURITY-TOKEN"]
    else:
        print("❌ 登录失败:", response.json())
        exit()
    ///
    
    for attempt in range(1, 4):
        try:
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                print("✅ 登录成功！")
                return response.headers["CST"], response.headers["X-SECURITY-TOKEN"]
            else:
                print(f"❌ 登录失败: {response.json()}")
        
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求错误: {e}")

        # 如果不是第一次尝试，打印重试信息
        if attempt < 3:
            print(f"🔄 正在重试... {attempt}/3")
            time.sleep(2)  # 等待2秒后重试
        else:
            print("⚠️ 达到最大重试次数，程序退出")
            exit()
"""

# ======== 获取市场数据 ========
def get_market_data(cst, security_token,epic,resolution):
    url = BASE_URL + f"prices/{epic}?resolution={resolution}&max=200"
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
            df["open"] = df["openPrice"].apply(lambda x: (x['bid'] + x['ask'])/2)
            df["close"] = df["closePrice"].apply(lambda x: (x['bid'] + x['ask'])/2)
            df["high"] = df["highPrice"].apply(lambda x: (x['bid'] + x['ask'])/2)
            df["low"]  = df["lowPrice"].apply(lambda x: (x['bid'] + x['ask'])/2)

            df["volume"] = df["lastTradedVolume"]

            # 只保留时间戳、收盘价、最高价和最低价，没有volume如需要可添加
            return df[["timestamp", "open","close", "high", "low","volume"]].set_index("timestamp")
        except ValueError as e:
            print("❌ 解析 JSON 失败:", e)
            return None
    else:
        print("❌ 获取市场数据失败:", response.status_code)
        return None  

# ======== 获取账户余额 ======== 
def get_account_balance(cst, token):
    """获取账户余额（适配 Capital.com）"""
    url = f"{BASE_URL}accounts"
    headers = {
        "CST": cst,
        "X-SECURITY-TOKEN": token
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        accounts = data.get("accounts", [])

        if accounts:
            account = accounts[0]  # 获取第一个账户
            balance_info = account.get("balance", {})

            return {
                "balance": float(balance_info.get("balance", 0.0)),
            }
        else:
            print("❌ 获取账户余额失败: 账户列表为空")
    else:
        print(f"❌ 获取账户余额失败: {response.status_code} - {response.text}")

    return None

# ======== 获取市场信息 ========
def get_market_info(epic,cst, token):
    url = f"{BASE_URL}markets/{epic}"
    headers = {"CST": cst, "X-SECURITY-TOKEN": token}
    response = requests.get(url, headers=headers)
    print(json.dumps(response.json(), indent=4))
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ 获取市场信息失败: {response.status_code} - {response.text}")
        return None

# ======== 获取仓位ID ========
def get_deal_id(deal_ref, cst, token):
    """获取订单ID（带重试机制）"""
    for _ in range(5):
        response = requests.get(
            f"{BASE_URL}confirms/{deal_ref}",
            headers={"CST": cst, "X-SECURITY-TOKEN": token}
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("dealStatus") == "ACCEPTED":
                return data.get("dealId")
        time.sleep(0.5)
    return None

def get_positions(cst, token):
    url = BASE_URL + "positions"
    headers = {"CST": cst, "X-SECURITY-TOKEN": token, "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('positions', [])
    else:
        print(f"❌ 获取持仓失败: {response.text}")
        return []

if __name__ == '__main__':
    cst,token=login()
    df=get_market_data(cst,token,"GOLD","HOUR")
    print(df)


