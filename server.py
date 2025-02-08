from flask import Flask

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return "Healthy", 200

def run_server():
    try:
        app.run(host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        print("\n🛑 服务器被手动终止")