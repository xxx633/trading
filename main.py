"""
# 主程序OK
from threading import Thread
import asyncio
from datetime import datetime,timedelta,timezone
from server import run_server  # Flask 服务器
from gold import *
from config import *


#半小时
def get_next_half_hour():
    now = datetime.now(timezone.utc)
    if now.minute < 30:
        next_time = now.replace(minute=30, second=5, microsecond=0)  # 进入下一半小时
    else:
        next_time = now.replace(minute=0, second=5, microsecond=0) + timedelta(hours=1)  # 进入下一小时整点

    return next_time

# 获取下一个小时的0分钟
def get_next_minute():
    now = datetime.now(timezone.utc)
    # 获取下一个小时的 0 分钟
    next_minute = now.replace(minute=5, second=5, microsecond=0)
    
    # 如果当前时间已经过了 XX:01（例如 12:02, 12:10），则需要调整为下一个小时的 0 分钟
    if now >= next_minute:
        next_minute = next_minute + timedelta(hours=1)
    
    return next_minute

async def wait_until(target_hour, target_minute):
    now = datetime.now(timezone.utc)
    target_time = now.replace(hour=target_hour, minute=target_minute, second=5, microsecond=0)

    if now >= target_time:
        target_time += timedelta(days=1)  # 如果已经过了这个时间，则等到第二天

    wait_seconds = (target_time - now).total_seconds()
    await asyncio.sleep(wait_seconds)

async def run_trading():   
    start_time = get_next_minute()
    while True:
        try:
            now = datetime.now(timezone.utc)
            weekday = now.weekday()  # 星期六 (0=星期一, 5=星期六)

            if weekday in [5, 6]:  # Saturday or Sunday
                # 等到下周一 00:05
                days_until_monday = 7 - weekday
                next_run = (now + timedelta(days=days_until_monday)).replace(hour=0, minute=5, second=5, microsecond=0)
                wait_seconds = (next_run - now).total_seconds()
                await asyncio.sleep(wait_seconds)
            
            elif 22 <= now.hour < 23:
                await wait_until(23, 5)  # 23:05 继续

            # 获取下一个小时的 00 分钟
            else:
                next_minute = get_next_minute()
                wait_seconds = (next_minute - datetime.now(timezone.utc)).total_seconds()
                await asyncio.sleep(wait_seconds)
            
            # 登录并获取 CST 和 X-SECURITY-TOKEN
            cst, security_token = login()

            # 运行交易策略
            
            gold(cst, security_token,now.hour)
            
            elapsed_time = datetime.now(timezone.utc) - start_time
            days = elapsed_time.days
            hours = elapsed_time.seconds // 3600
            minutes = (elapsed_time.seconds % 3600) // 60

            # 打印格式化时间为 "xx天xx小时xx分钟"
            print(f"⏳ 已运行 {days}天 {hours}小时 {minutes}分钟")

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
#TEST
import asyncio
from config import login,LoginError
from datetime import timedelta,timezone,datetime
from gold import *
from kriora import *


async def align_first_run():
    """等待到下一次 5 分钟倍数（05, 10, 15…）"""
    now = datetime.now(timezone.utc)
    # 下一个 5 分钟倍数
    next_minute = (now.minute // 5 + 1) * 5
    if next_minute >= 60:
        # 跳到下一小时
        next_hour = now.hour + 1
        next_time = now.replace(hour=next_hour % 24, minute=0, second=0, microsecond=0)
    else:
        next_time = now.replace(minute=next_minute, second=0, microsecond=0)
    wait_seconds = (next_time - now).total_seconds()
    await asyncio.sleep(wait_seconds)

async def trading_loop():
    trade_count = 0
    last_access_time = None
    cst = token = None

    # 首次对齐
    await align_first_run()

    while True:
        now = datetime.now(timezone.utc)

        # 周末跳过
        if now.weekday() >= 5:
            print("🌙 周末休息，等待下周一...")
            days_until_monday = 7 - now.weekday()
            next_run = (now + timedelta(days=days_until_monday)).replace(hour=0, minute=5, second=0, microsecond=0)
            last_access_time = None  # 周末结束后第一次访问必须重新登录
            await asyncio.sleep((next_run - now).total_seconds())
            continue

        # 每天 22-23 点休息
        if 22 <= now.hour < 23:
            print("🌙 每天 22-23 点休息，等待 23:05...")
            next_run = now.replace(hour=23, minute=5, second=0, microsecond=0)
            last_access_time = None  # 23 点后第一次访问必须重新登录
            await asyncio.sleep((next_run - now).total_seconds())
            continue

        # 判断是否需要登录
        need_login = False
        if not last_access_time:
            # 第一次访问或特殊情况
            need_login = True
        elif (now - last_access_time) > timedelta(minutes=15):
            # 超过 15 分钟没访问
            need_login = True

        if need_login:
            try:
                cst, token = login()
            except LoginError as e:
                print(e)
                await asyncio.sleep(60)  # 等 1 分钟再重试
                continue  # 继续下一轮循环
            print(f"🔑 已登录，时间: {now.strftime('%H:%M:%S')}")

        # 执行策略
        kriora(cst, token)
        trade_count += 1
        print(f"⏳ 等待 5 分钟后执行第 {trade_count} 次交易...\n----------------------")

        # 更新最后访问时间
        last_access_time = datetime.now(timezone.utc)

        # 等待 5 分钟
        await asyncio.sleep(300)

