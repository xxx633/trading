from .rsi_ema_macd import *

# ======== 交易策略函数 ========
#做多：EMA金叉，MACD金叉，RSI30-50, bb下轨-中轨
#做空：EMA死叉，MACD死叉，RSI70-50, bb上轨-中轨
def rsi_ema_macd(cst, security_token):
    df = get_market_data(cst, security_token, EPIC, TIMEFRAME)
    if df is None:
        return
    
    df = compute_indicators(df)
    current = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else current

    # 获取趋势方向：当前价格与 EMA50 的位置关系
    #trend_up = current['close'] > current['ema50']
    #trend_down = current['close'] < current['ema50']

    # --- EMA 策略 ---
    if current['ema9'] > current['ema21'] and prev['ema9'] <= prev['ema21']:
        if deal_positions["ema"]["sell"]:  # 先平空仓
            close_position(cst, security_token, "ema", "SELL")
        if not deal_positions["ema"]["buy"]: #and trend_up:  # 趋势向上时开多仓
            open_position(cst, security_token, "BUY", "EMA金叉", "ema")
            
    elif current['ema9'] < current['ema21'] and prev['ema9'] >= prev['ema21']:
        if deal_positions["ema"]["buy"]:  # 先平多仓
            close_position(cst, security_token, "ema", "BUY")
        if not deal_positions["ema"]["sell"]:# and trend_down:  # 趋势向下时开空仓
            open_position(cst, security_token, "SELL", "EMA死叉", "ema")


    # --- MACD 策略 ---
    if current['macd_line'] > current['macd_signal'] and prev['macd_line'] <= prev['macd_signal']:
        if deal_positions["macd"]["sell"]:  # 先平空仓
            close_position(cst, security_token, "macd", "SELL")
        if not deal_positions["macd"]["buy"] :#and trend_up:  # 趋势向上时开多仓
            open_position(cst, security_token, "BUY", "MACD金叉", "macd")
            
    elif current['macd_line'] < current['macd_signal'] and prev['macd_line'] >= prev['macd_signal']:
        if deal_positions["macd"]["buy"]:  # 先平多仓
            close_position(cst, security_token, "macd", "BUY")
        if not deal_positions["macd"]["sell"] :#and trend_down:  # 趋势向下时开空仓
            open_position(cst, security_token, "SELL", "MACD死叉", "macd")

    # --- RSI 策略 ---
    # 多头信号：RSI 低于 30 时开多仓；RSI 高于 50 时平多仓
    if current['rsi'] < 30:
        if len(deal_positions["rsi"]["buy"]) < MAX_RSI_POSITIONS :#and trend_up:  # 趋势向上时开多仓
            open_position(cst, security_token, "BUY", "RSI低于30买入", "rsi")
    elif current['rsi'] > 50:
        for _ in deal_positions["rsi"]["buy"][:]:
            close_position(cst, security_token, "rsi", "BUY")
    
    # 空头信号：RSI 高于 70 时开空仓；RSI 低于 50 时平空仓
    if current['rsi'] > 70:
        if len(deal_positions["rsi"]["sell"]) < MAX_RSI_POSITIONS:# and trend_down:  # 趋势向下时开空仓
            open_position(cst, security_token, "SELL", "RSI高于70卖出", "rsi")
    elif current['rsi'] < 50:
        for _ in deal_positions["rsi"]["sell"][:]:
            close_position(cst, security_token, "rsi", "SELL")


    # --- 布林带策略 ---
    # 若收盘价超过上轨，则：
    if current['close'] > current['bb_upper']:
        if deal_positions["bb"]["buy"]:
            close_position(cst, security_token, "bb", "BUY")
        if not deal_positions["bb"]["sell"]:# and trend_down:  # 趋势向下时开空仓
            open_position(cst, security_token, "SELL", "BB上轨卖出", "bb")
    # 若收盘价低于下轨，则：
    elif current['close'] < current['bb_lower']:
        if deal_positions["bb"]["sell"]:
            close_position(cst, security_token, "bb", "SELL")
        if not deal_positions["bb"]["buy"]:#and trend_up:  # 趋势向上时开多仓
            open_position(cst, security_token, "BUY", "BB下轨买入", "bb")
    
    # 布林带止盈逻辑：
    # 对于空仓：当收盘价跌破中轨，则平仓止盈
    if deal_positions["bb"]["sell"] and current['close'] < current['bb_mid']:
        close_position(cst, security_token, "bb", "SELL")
    # 对于多仓：当收盘价突破中轨，则平仓止盈
    if deal_positions["bb"]["buy"] and current['close'] > current['bb_mid']:
        close_position(cst, security_token, "bb", "BUY")