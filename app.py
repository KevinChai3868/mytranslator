# app.py —— 整支檔案先分成 10 區，之後每一章填其中一區
import os
from io import BytesIO

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from dotenv import load_dotenv

from providers import (
    ask_travel_assistant,
    convert_currency,
    get_weather,
    synthesize_speech,
    translate,
    translate_image,
)

# ===== 1. 設定與金鑰 =====   （CH04，這章先放一點）
load_dotenv()                      # 讀取 .env 裡的設定
app = Flask(__name__)

# ===== 2. 翻譯 API =====          （CH06 會填 /api/translate）
@app.route('/api/translate', methods=['POST'])
def api_translate():
    data = request.get_json(silent=True) or {}
    result = translate(data)
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code

# ===== 3. 朗讀 TTS API =====      （CH08 會填 /api/tts）
@app.route('/api/tts', methods=['POST'])
def api_tts():
    data = request.get_json(silent=True) or {}
    result = synthesize_speech(data)

    if not result.get('ok'):
        return jsonify(result), 400

    return send_file(
        BytesIO(result['audio']),
        mimetype=result.get('mime_type', 'audio/mpeg'),
        as_attachment=False,
        download_name='translation.mp3',
    )

# ===== 4. 即時語音 SocketIO =====（CH09 會填）
# ===== 5. 拍照 / 檔案 API =====   （CH11–12 會填）
@app.route('/api/translate-image', methods=['POST'])
def api_translate_image():
    data = request.get_json(silent=True) or {}
    result = translate_image(data)
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code

# ===== 6. 匯率 API =====          （CH13 會填 /api/currency）
@app.route('/api/currency', methods=['POST'])
def api_currency():
    data = request.get_json(silent=True) or {}
    result = convert_currency(data)
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code

# ===== 7. 天氣 API =====          （CH14 會填 /api/weather）
@app.route('/api/weather', methods=['POST'])
def api_weather():
    data = request.get_json(silent=True) or {}
    result = get_weather(data)
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code

# ===== 8. 旅遊助手 API =====      （CH15 會填）
@app.route('/api/ask', methods=['POST'])
def api_ask():
    data = request.get_json(silent=True) or {}
    result = ask_travel_assistant(data)
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code

# ===== 9. PWA 與路由 =====        （CH16 會填 / 與靜態檔）

# ===== 10. 啟動 =====
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health')
def health():
    return jsonify({'ok': True})

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js')

if __name__ == '__main__':
    port = int(os.getenv('PORT', '5001'))
    app.run(host='0.0.0.0', port=port, debug=True)
