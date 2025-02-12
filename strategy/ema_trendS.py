from .ema_trend import *

# 在策略执行时调用动态止盈更新函数
#EMA 趋势反转 动态止盈
def ema_trend(cst, security_token):
    df_lower = get_market_data(cst, security_token,EPIC,LOWER)
    df_higher = get_market_data(cst, security_token,EPIC,HIGHER)
    
    if df_lower is None or df_higher is None or df_lower.empty or df_higher.empty:
        print("❌ K线数据为空，无法计算指标")
        return
    df_lower = calculate_indicators(df_lower)
    df_higher["sma50"] = df_higher["close"].rolling(50).mean()
    
    # 计算趋势方向
    trend_up = df_higher["close"].iloc[-1] > df_higher["sma50"].iloc[-1]
    trend_down = df_higher["close"].iloc[-1] < df_higher["sma50"].iloc[-1]
    
    # 计算趋势反转信号
    trend_up_reversal = df_higher["close"].iloc[-2] <= df_higher["sma50"].iloc[-2] and trend_up
    trend_down_reversal = df_higher["close"].iloc[-2] >= df_higher["sma50"].iloc[-2] and trend_down
    
    position = get_position(cst, security_token)
    
    # 更新动态止盈
    global trailing_stop_price
    trailing_stop_price = update_trailing_stop(cst, security_token)
    
    if trend_up_reversal and position and position.get("direction") == "SELL":
        close_position(cst, security_token)
    elif trend_down_reversal and position and position.get("direction") == "BUY":
        close_position(cst, security_token)
    
    if not position:
        df_lower["prev_fast_ema"] = df_lower["fast_ema"].shift(1)
        df_lower["prev_slow_ema"] = df_lower["slow_ema"].shift(1)
        ema_long_cross = (df_lower["prev_fast_ema"] <= df_lower["prev_slow_ema"]) & (df_lower["fast_ema"] > df_lower["slow_ema"])
        ema_short_cross = (df_lower["prev_fast_ema"] >= df_lower["prev_slow_ema"]) & (df_lower["fast_ema"] < df_lower["slow_ema"])
        
        if ema_long_cross.iloc[-1] and trend_up:
            open_position("BUY", cst, security_token)
        elif ema_short_cross.iloc[-1] and trend_down:
            open_position("SELL", cst, security_token)
