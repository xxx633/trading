from threading import Thread
import asyncio
from server import run_server  # 从 server.py 导入 run_server 函数
from trading import login, trading_strategy

async def run_trading():
    cst, security_token = login()
    while True:
        try:
            print("\n📊 检查交易信号...")
            trading_strategy(cst, security_token)
            print("⏳ 等待 16 分钟...")
            print("----------------------")
            await asyncio.sleep(960)  # 16 分钟（异步等待）
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
