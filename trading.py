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
   # =============== 检查会话是否有效 ===============
def check_session(cst, security_token):
    url = BASE_URL + "session"
    headers = {"CST": cst, "X-SECURITY-TOKEN": security_token, "Content-Type": "application/json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 401:  # 401 表示会话过期
        print("🔄 会话过期，重新登录...")
        return login()
    
    return cst, security_token

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


def calculate_ema(df, period):
    return df["close"].ewm(span=period, adjust=False).mean()

def place_order(cst, security_token, direction):

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

def trading_strategy(cst, security_token):
    
        # =====================
        # 1. 获取多时间框架数据
        # =====================
        # 获取日线数据（趋势过滤）
        global TIMEFRAME
        original_timeframe = TIMEFRAME  # 保存原始时间框架
        TIMEFRAME = "DAY"  # 临时修改为日线
        daily_df = get_market_data(cst, security_token)
        
        # 获取15分钟数据（信号生成）
        TIMEFRAME = "MINUTE_15"  # 修改为15分钟
        m15_df = get_market_data(cst, security_token)
        TIMEFRAME = original_timeframe  # 恢复原始设置
        
        if daily_df is None or m15_df is None or len(daily_df)<50 or len(m15_df)<21:
            print("⚠️ 数据不足，等待更多K线")
            return
        
        # =====================
        # 2. 计算技术指标
        # =====================
        # 日线指标
        daily_df["SMA50"] = daily_df["close"].rolling(50).mean()
        
        # 15分钟指标
        m15_df["EMA9"] = calculate_ema(m15_df, 9)
        m15_df["EMA21"] = calculate_ema(m15_df, 21)
        
        # =====================
        # 3. 趋势状态判断
        # =====================
        current_daily_close = daily_df["close"].iloc[-1]
        current_daily_sma = daily_df["SMA50"].iloc[-1]
        trend_direction = "UP" if current_daily_close > current_daily_sma else "DOWN"
        
        # =====================
        # 4. 趋势反转检测
        # =====================
        if len(daily_df) >= 2:
            prev_daily_close = daily_df["close"].iloc[-2]
            prev_daily_sma = daily_df["SMA50"].iloc[-2]
            
            # 多头反转信号（下穿转上穿）
            if prev_daily_close < prev_daily_sma and current_daily_close > current_daily_sma:
                print("‼️ 日线趋势反转：多头信号")
                place_order(cst, security_token, "BUY")
                
            # 空头反转信号（上穿转下穿）
            elif prev_daily_close > prev_daily_sma and current_daily_close < current_daily_sma:
                print("‼️ 日线趋势反转：空头信号")
                place_order(cst, security_token, "SELL")
        
        # =====================
        # 5. 常规EMA交叉信号（带趋势过滤）
        # =====================
        if len(m15_df) >= 2:
            # 获取最近两根K线
            prev_ema9 = m15_df["EMA9"].iloc[-2]
            prev_ema21 = m15_df["EMA21"].iloc[-2]
            current_ema9 = m15_df["EMA9"].iloc[-1]
            current_ema21 = m15_df["EMA21"].iloc[-1]
            
            # 金叉信号（且趋势向上）
            if prev_ema9 < prev_ema21 and current_ema9 > current_ema21 and trend_direction == "UP":
                print("💹 EMA金叉（趋势向上）：买入")
                place_order(cst, security_token, "BUY")
                
            # 死叉信号（且趋势向下）
            elif prev_ema9 > prev_ema21 and current_ema9 < current_ema21 and trend_direction == "DOWN":
                print("📉 EMA死叉（趋势向下）：卖出")
                place_order(cst, security_token, "SELL")
            else:
                print("📊 当前趋势方向：{} | 无有效交叉信号".format(trend_direction))
