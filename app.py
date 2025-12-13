from flask import Flask, request, send_file, jsonify, render_template
from flask_cors import CORS
from PIL import Image
import io
import json
import os

# 引入我們分離出去的核心邏輯
from core.stego import encode_image, decode_image, StegoError

app = Flask(__name__)
CORS(app)

# 設定最大上傳限制 (例如 16MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

@app.route('/')
def index():
    # Flask 標準做法是將 HTML 放在 templates 資料夾
    return render_template('index.html')

@app.route('/encode', methods=['POST'])
def handle_encode():
    try:
        file = request.files.get('image')
        message = request.form.get('message')
        bit_map_str = request.form.get('bit_map') 
        
        if not file or not message or not bit_map_str:
            return jsonify({"error": "缺少必要資料"}), 400
        
        bit_map = json.loads(bit_map_str)
        bit_map.sort(key=lambda x: (x['b'], x['c']))
        
        img = Image.open(file.stream)
        
        # 呼叫核心邏輯
        secret_img = encode_image(img, message, bit_map)
        
        output_buffer = io.BytesIO()
        secret_img.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        
        return send_file(
            output_buffer, 
            mimetype='image/png', 
            as_attachment=True, 
            download_name='stego_result.png'
        )

    except StegoError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "伺服器內部錯誤"}), 500

@app.route('/decode', methods=['POST'])
def handle_decode():
    try:
        file = request.files.get('image')
        bit_map_str = request.form.get('bit_map')
        
        if not file or not bit_map_str:
            return jsonify({"error": "資料不完整"}), 400

        img = Image.open(file.stream).convert("RGB")
        bit_map = json.loads(bit_map_str)
        bit_map.sort(key=lambda x: (x['b'], x['c']))
        
        msg = decode_image(img, bit_map)
        
        if msg:
            return jsonify({"message": msg})
        else:
            return jsonify({"message": "解密失敗：密碼錯誤或無訊息"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/auto_decode', methods=['POST'])
def handle_auto_decode():
    try:
        file = request.files.get('image')
        if not file: return jsonify({"error": "未上傳圖片"}), 400
        
        img = Image.open(file.stream).convert("RGB")
        
        # 定義常見策略
        suspects = [
            ("標準 LSB (RGB Bit 0)", [{'c':0,'b':0}, {'c':1,'b':0}, {'c':2,'b':0}]),
            ("僅紅色 R0", [{'c':0,'b':0}]),
            ("僅綠色 G0", [{'c':1,'b':0}]),
            ("僅藍色 B0", [{'c':2,'b':0}]),
            ("無紅模式 (G0, B0)", [{'c':1,'b':0}, {'c':2,'b':0}])
        ]
        
        # 執行暴力破解
        for name, bit_map in suspects:
            bit_map.sort(key=lambda x: (x['b'], x['c']))
            msg = decode_image(img, bit_map)
            if msg:
                return jsonify({
                    "success": True,
                    "strategy": name,
                    "message": msg,
                    "found_map": bit_map
                })
        
        return jsonify({"success": False, "message": "自動破解失敗"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # 讓 Gunicorn 可以在生產環境找到 app，開發環境用 debug
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)