from openai import OpenAI
import requests
import pandas as pd
import pandas_ta as ta
import numpy as np
from config import *

import logging

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)


client = OpenAI(
    base_url="https://api.kriora.com/v1",
    api_key="sk-O0uhdrmigKPM-e2F_Npm_5kpW-sOUzLiKVY4UP83zOlFSzUd"#os.environ.get("KRIORA_API_KEY")
)

SYSTEM_PROMT="""You are a professional intraday trader.Do not force trades.Return ONLY one word: BUY, SELL, or NO_TRADE."""

def calculate_position_size(current_price,balance):
    capital=balance*11.7

    size=capital/current_price

    return round(size,2)

def calculate_indicators(cst,token):
    df=get_market_data(cst,token,"GOLD","MINUTE_5")

    df['EMA13'] = ta.ema(df['close'], length=13)
    df['EMA21'] = ta.ema(df['close'], length=21)
    df['EMA144'] = ta.ema(df['close'], length=144)
    df['EMA169'] = ta.ema(df['close'], length=169)
    df['RSI14'] = ta.rsi(df['close'], length=14)

    return df

def place_order(cst,token,sig,df):
    current_price = df["close"].iloc[-1]

    account = get_account_balance(cst, token)
    if not account:
        return
    logger.info(f"💰 账户余额: {account['balance']}")

    size=calculate_position_size(current_price,account["balance"])

    if sig == "BUY":
        tp = current_price + 5.87
        sl=current_price - 5.87
    else:
        tp = current_price - 5.87
        sl=current_price + 5.87

    order = {
        "epic": "GOLD",
        "direction": sig,
        "size": size,
        "orderType": "MARKET",
        "profitLevel": tp,
        "stopLevel": sl,
        "guaranteedStop": False,
        "oco": False         # 没有止损就不启用 OCO
    }

    response = requests.post(
        f"{BASE_URL}positions",
        headers={"CST": cst, "X-SECURITY-TOKEN": token},
        json=order
    )

    if response.status_code == 200:
        logger.info(f"✅ {sig} 下单成功 | 数量: {size} | 价格: {current_price:.2f} | 止盈: {tp:.2f} | 止损: {sl:.2f}")
    else:
        logger.info(f"❌ 下单失败: {response.status_code} - {response.text}")

def kriora(cst,token):
    if get_positions(cst, token):
        logger.info("🟡 当前已有持仓，跳过开仓信号")
        return

    df=calculate_indicators(cst,token)
    recent_df=df.tail(30)
    features = recent_df[['open', 'high', 'low', 'close', 'volume', 'EMA13', 'EMA21','EMA144', 'EMA169', 'RSI14']]
    data_json = features.to_dict(orient="records")

    completion = client.chat.completions.create(
        model="deepseek/deepseek-r1-0528",
        messages = [{"role": "system","content":SYSTEM_PROMT},
                    {"role": "user","content": f"""Timeframe: 5-minute.
                        Indicators:EMA 13, 21, 144, 169 ,RSI 14,Last 30 OHLCV candles:
                        {data_json}
                        Evaluate market structure, not price prediction.
                        Focus on EMA alignment, expansion vs compression, price location, RSI confirmation, and volume participation.
                        Decide BUY, SELL, or NO_TRADE based on this data.
                        """}  
                    ],
        temperature=0
    )

    #print(completion.choices[0].message)
    signal=completion.choices[0].message.content.strip()

    if signal=="NO_TRADE":
        logger.info("NO_SIGNAL")
        return
    elif signal=="BUY":
        place_order(cst,token,"BUY",df)
    elif signal=="SELL":
        place_order(cst,token,"SELL",df)

    
