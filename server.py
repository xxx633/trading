# server.py
import asyncio
from flask import Flask
from main import trading_loop
import logging

logging.basicConfig(level=logging.INFO,format="%(message)s")
logger=logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/")
def root():
    return "root ok", 200

@app.route("/health")
def health():
    return "health ok", 200

logger.info("🚀 程序启动了！")

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.create_task(trading_loop())

logger.info("🎯 交易循环已创建任务")

def start_loop():
    try:
        loop.run_forever()
    except RuntimeError:
        pass  # 避免 Gunicorn 再次创建事件循环时报错

import threading
threading.Thread(target=start_loop, daemon=True).start()

"""
if __name__ == "__main__":
    # Windows 本地测试
    from threading import Thread
    # 关闭 debug reloader 防止 signal 错误
    t = Thread(target=lambda: app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False), daemon=True)
    t.start()
    # 运行事件循环
    loop.run_forever()
"""