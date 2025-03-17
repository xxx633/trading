#不可更改
import threading
import time
import requests
import asyncio
import aiohttp
from flask import Flask

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return "Healthy", 200

def keep_awake():
    url="http://small-viola-vanny-f71cc402.koyeb.app/health"
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url) as response:
                    print(f"Sent keep-alive request,status code:{response.status_code}")
            except Exception as e:
                print(f"Request failed:{e}")
    
            await asyncio.sleep(900)

def run_server():
    loop=asyncio.get_event_loop()
    try:
        loop.create_task(keep_awake())
        
        app.run(host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        print("\n🛑 服务器被手动终止")
