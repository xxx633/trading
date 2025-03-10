# 主程序
from threading import Thread
import asyncio
from datetime import datetime,timedelta
from server import run_server  # Flask 服务器
from strategy import *
from config import login

def get_next_half_hour():
    now = datetime.now()
    if now.minute < 30:
        next_time = now.replace(minute=30, second=5, microsecond=0)  # 进入下一半小时
    else:
        next_time = now.replace(minute=0, second=5, microsecond=0) + timedelta(hours=1)  # 进入下一小时整点

    return next_time
# 获取下一个小时的0分钟
def get_next_minute():
    now = datetime.now()
    # 获取下一个小时的 0 分钟
    next_minute = now.replace(minute=0, second=5, microsecond=0)
    
    # 如果当前时间已经过了 XX:01（例如 12:02, 12:10），则需要调整为下一个小时的 0 分钟
    if now >= next_minute:
        next_minute = next_minute + timedelta(hours=1)
    
    return next_minute

async def wait_until(target_hour, target_minute):
    now = datetime.now()
    target_time = now.replace(hour=target_hour, minute=target_minute, second=5, microsecond=0)

    if now >= target_time:
        target_time += timedelta(days=1)  # 如果已经过了这个时间，则等到第二天

    wait_seconds = (target_time - now).total_seconds()
    await asyncio.sleep(wait_seconds)

async def run_trading():   
    #trade_count = 0  # 初始化交易次数计数器
    start_time = get_next_half_hour()
    while True:
        try:
            now = datetime.now()
            is_saturday = now.weekday() == 5  # 星期六 (0=星期一, 5=星期六)

            # 处理额外的交易时间：
            if now.hour == 20 and now.minute == 30:  # 每天 23:05 额外触发
                await wait_until(21, 5)
            elif is_saturday and now.hour in [5, 6]:  # 星期六 7:00 和 8:00 跳过
                await wait_until(7, 0)  # 跳过到 9:00 执行
            else:
                # 获取下一个小时的 00 分钟
                next_minute = get_next_half_hour()
                wait_seconds = (next_minute - datetime.now()).total_seconds()
                await asyncio.sleep(wait_seconds)
            
            # 登录并获取 CST 和 X-SECURITY-TOKEN
            cst, security_token = login()

            # 运行交易策略
            #rsi_ema_macd(cst, security_token)
            #ema_trend(cst, security_token)
            mta(cst, security_token)
            
            elapsed_time = datetime.now() - start_time
            days = elapsed_time.days
            hours = elapsed_time.seconds // 3600
            minutes = (elapsed_time.seconds % 3600) // 60

            # 打印格式化时间为 "xx天xx小时xx分钟"
            print(f"⏳ 已运行 {days}天 {hours}小时 {minutes}分钟")
            #print(f"⏳ 等待执行第{trade_count + 1}次交易交易")
            #trade_count += 1

        except KeyboardInterrupt:
            print("\n🛑 交易中断，退出程序")
            break


if __name__ == "__main__":
    try:
        # 在新线程中运行 Flask 服务器
        flask_thread = Thread(target=run_server)
        flask_thread.daemon = True  # 使 Flask 线程在主线程退出时自动结束
        flask_thread.start()

        # 启动交易（确保异步运行）
        asyncio.run(run_trading())

    except KeyboardInterrupt:
        print("\n🛑 主程序被手动中断，退出程序")



"""
from threading import Thread
import asyncio
from server import run_server  # Flask 服务器
from config import login
from strategy import *

async def run_trading():
    trade_count = 0  # 初始化交易次数计数器
    while True:
        try:
            cst, security_token = login()
            
            while True:        
                # 运行交易策略
                #普通
                #ema_trend(cst, security_token)

                mta(cst, security_token)
                #deepseek(cst,security_token)
                print(f"⏳ 等待 1 分钟后执行第{trade_count + 1}次交易...\n----------------------")
                #等待下一次执行
                await asyncio.sleep(60)

                # 更新交易次数
                trade_count += 1

        except KeyboardInterrupt:
            print("\n🛑 交易中断，退出程序")
            break

if __name__ == "__main__":
    try:
        # 在新线程中运行 Flask 服务器
        flask_thread = Thread(target=run_server)
        flask_thread.daemon = True  
        flask_thread.start()

        # 启动交易
        asyncio.run(run_trading())

    except KeyboardInterrupt:
        print("\n🛑 主程序被手动中断，退出程序")

"""
