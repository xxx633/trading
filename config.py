import requests
import pandas as pd
import time 
import numpy as np
import os
# ======== 配置部分 ========
API_KEY = os.getenv('API')
CLIENT_IDENTIFIER = os.getenv('EMAIL')
PASSWORD = "Password2@123"
BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1/"
MIN_SIZE=1

# ======== 登录函数 ========
def login():
    url = BASE_URL + "session"
    headers = {"X-CAP-API-KEY": API_KEY, "Content-Type": "application/json"}
    payload = {"identifier": CLIENT_IDENTIFIER, "password": PASSWORD, "encryptedPassword": False}
    
    """
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        print("✅ 登录成功！")
        return response.headers["CST"], response.headers["X-SECURITY-TOKEN"]
    else:
        print("❌ 登录失败:", response.json())
        exit()
    """
    
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

            df["close"] = df["closePrice"].apply(lambda x: round(x["bid"], 3))
            df["high"] = df["highPrice"].apply(lambda x: round(x["bid"], 3))
            df["low"] = df["lowPrice"].apply(lambda x: round(x["bid"], 3))
            #df["volume"] = df["lastTradedVolume"]

            # 只保留时间戳、收盘价、最高价和最低价，没有volume如需要可添加
            return df[["timestamp", "close", "high", "low"]].set_index("timestamp")
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
    #print(json.dumps(response.json(), indent=4))
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

# ======== 获取回测数据 ========
def get_historical_prices(cst_token,security_token):
    # 设定 API 端点和固定参数
    epic = "XRPUSD"  # 你要查询的 Instrument Epic
    resolution = "HOUR"  # 分辨率
    max_results = 1000  # 返回最大数据量
    from_date = "2024-11-24T00:00:00"  # 起始日期
    to_date = "2024-12-24T00:00:00"  # 结束日期

    # 设定请求的 URL 和参数
    url = f"https://api-capital.backend-capital.com/api/v1/prices/{epic}"
    params = {
        "resolution": resolution,
        "max": max_results,
        "from": from_date,
        "to": to_date
    }

    # 请求头
    headers = {
        'X-SECURITY-TOKEN': security_token,
        'CST': cst_token
    }

    # 发送 GET 请求
    response = requests.get(url, params=params, headers=headers)

    # 检查响应是否成功
    if response.status_code == 200:
        try:
            data = response.json()["prices"]

            if not data:
                print("❌ 没有返回价格数据")
                return None
            
            df = pd.DataFrame(data)
            df["timestamp"] = pd.to_datetime(df["snapshotTime"])

            df["close"] = df["closePrice"].apply(lambda x: x["bid"] if isinstance(x, dict) else None)
            df["high"] = df["highPrice"].apply(lambda x: x["bid"] if isinstance(x, dict) else None)
            df["low"] = df["lowPrice"].apply(lambda x: x["bid"] if isinstance(x, dict) else None)
            df["volume"] = df["lastTradedVolume"].apply(lambda x: x if isinstance(x, int) else None)  # 添加 volume 列

            #df.to_csv('historical_data.csv', encoding='utf-8')
            #print("✅ 数据已成功保存为 CSV 文件")

            # 只保留时间戳、收盘价、最高价、最低价和成交量
            return df[["timestamp", "close", "high", "low", "volume"]].set_index("timestamp")
        except ValueError as e:
            print("❌ 解析 JSON 失败:", e)
            return None
    else:
        print(f"请求失败，状态码：{response.status_code}, 错误信息：{response.text}")

# ======== 获取动态仓位 ========
def dynamic_position_sizing(current_price, atr, balance, adx):
    """带最小交易量限制的仓位管理"""
    try:
        if atr <= 0 or current_price <= 0:
            raise ValueError("无效的价格或ATR值")
            
        # 波动率因子 (0.5-2%波动对应1.5-0.5倍仓位)
        volatility_factor = np.interp(atr/current_price*100, [0.5, 2.0], [1.5, 0.5])
        # 趋势强度因子 (20-60强度对应0.5-1.5倍仓位)
        trend_factor = np.interp(adx, [20, 60], [0.5, 1.5])
        # 每笔最多损失账户的2%
        RISK_PERCENT=2
        LEVERAGE=1
        adjusted_risk = RISK_PERCENT * volatility_factor * trend_factor
        risk_amount = max(balance * adjusted_risk / 100, 1)
        
        STOP_MULTIPLIER = 1.5
        dollar_risk = atr * current_price * STOP_MULTIPLIER
        if dollar_risk <= 0.01:
            return MIN_SIZE
            
        size = risk_amount / dollar_risk
        
        # 应用最小交易量限制
        
        size = max(round(size, 2), MIN_SIZE)
        max_size = balance * LEVERAGE / current_price
        return round(min(size, max_size))
        
    except Exception as e:
        print(f"仓位计算错误: {str(e)}，使用最小交易量")
        return MIN_SIZE

if __name__ == '__main__':
    print(dynamic_position_sizing(2.5,0.033,200,36))
