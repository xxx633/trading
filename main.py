# 主程序
from threading import Thread
import asyncio
from datetime import datetime,timedelta
from server import run_server  # Flask 服务器
from trading import trading_strategy
from config import login

# 获取下一个小时的1分钟
def get_next_minute():
    now = datetime.now()
    # 获取下一个小时的 1 分钟
    next_minute = now.replace(minute=1, second=0, microsecond=0)
    
    # 如果当前时间已经过了 XX:01（例如 12:02, 12:10），则需要调整为下一个小时的 1 分钟
    if now >= next_minute:
        next_minute = next_minute + timedelta(hours=1)
    
    return next_minute

async def run_trading():   
    trade_count = 0  # 初始化交易次数计数器
    
    while True:
        try:

            # 获取下一个小时的1分钟
            next_minute = get_next_minute()
            wait_seconds = (next_minute - datetime.now()).total_seconds()
            wait_minutes = wait_seconds // 60  # 计算等待的分钟数

            # 打印当前时间和等待的时间
            current_time = datetime.now().strftime("%H:%M")  # 获取当前时间的格式为小时:分钟
            next_minute_time = next_minute.strftime("%H:%M")  # 获取下一个1分钟的时间，去掉日期
            print(f"⏰当前时间: {current_time}\n⏳ 等待 {int(wait_minutes)} 分钟到 {next_minute_time} 执行第{trade_count + 1}次交易...")

            # 等待直到下一个小时的第一分钟
            await asyncio.sleep(wait_seconds)
            
            cst, security_token = login()

            # 运行交易策略
            print("\n📊 检查交易条件...")
            trading_strategy(cst, security_token)
            print(f"⏳ 等待下一个小时...")  # 可以调整为稍微改动后的信息
            print("----------------------")
            
            # 更新交易次数
            trade_count += 1

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


""""
#测试程序
from threading import Thread
import asyncio
from datetime import datetime
from server import run_server  # Flask 服务器
from trading import trading_strategy
from config import login

async def run_trading():
    trade_count = 0  # 初始化交易次数计数器
    while True:
        try:
            cst, security_token = login()
            
            while True:        
                # 运行交易策略
                trading_strategy(cst, security_token)
                
                print(f"⏳ 等待 1 分钟后执行第{trade_count + 1}次交易交易...\n----------------------")
                
                # 等待 60 秒再执行下一次
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