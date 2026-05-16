import os
import json
import base64
import requests
import traceback
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# ==========================================
# CẤU HÌNH API KEYS (Đã bảo mật theo biến môi trường)
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = "7061902150:AAFmEcywGZc-z6inJKgQX6bCIpkSngFc"
TELEGRAM_CHAT_ID = "5871331291"

genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# TỰ ĐỘNG KẾT NỐI MODEL AI PHÙ HỢP
# ==========================================
valid_models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
if 'gemini-1.5-flash' in valid_models:
    chosen_model = 'gemini-1.5-flash'
elif 'gemini-pro' in valid_models:
    chosen_model = 'gemini-pro'
else:
    chosen_model = valid_models[0]

model = genai.GenerativeModel(chosen_model)
print(f"🧠 MINDGUARD ĐÃ KẾT NỐI VỚI MODEL: {chosen_model}")

# ==========================================
# HÀM GỬI CẢNH BÁO TELEGRAM (DANGER)
# ==========================================
def send_alert(msg, reply):
    text = f"🚨 CẢNH BÁO MỨC ĐỘ NGUY HIỂM! \nHọc sinh: {msg}\nBot: {reply}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
    except:
        pass

# ==========================================
# HÀM XỬ LÝ LÕI AI GEMINI (ĐÃ THÊM MÀNG LỌC JSON CHỐNG LỖI)
# ==========================================
def get_ai_response(user_input):
    prompt = f"""Bạn là chuyên gia tâm lý MindGuard AI. Hãy phản hồi: '{user_input}'.
    CHỈ TRẢ VỀ ĐÚNG 1 ĐOẠN JSON, KHÔNG THÊM BẤT KỲ CHỮ HAY KÝ TỰ NÀO KHÁC XUNG QUANH:
    {{"level": "Safe/Warning/Danger", "reply": "nội dung"}}"""
    
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        # In kết quả gốc ra màn hình Log của Render để theo dõi
        print("\n=== AI TRẢ VỀ GỐC ===", flush=True)
        print(raw_text, flush=True) 
        print("=====================\n", flush=True)
        
        # Màng lọc JSON: Tự động dò tìm và cắt lấy phần nằm trong ngoặc {}
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_json_str = raw_text[start_idx:end_idx+1]
            return json.loads(clean_json_str)
        else:
            # Báo lỗi thẳng ra màn hình chat nếu AI lách luật không trả về JSON
            return {"level": "Error", "reply": f"Lỗi định dạng AI: {raw_text}"}
            
    except Exception as e:
        # Báo lỗi thẳng ra màn hình chat nếu gặp trục trặc hệ thống (hết quota, rớt mạng...)
        print(f"\n=== LỖI HỆ THỐNG: {str(e)} ===\n", flush=True)
        return {"level": "Error", "reply": f"Lỗi hệ thống: {str(e)}"}

# ==========================================
# CÁC ROUTE CỦA GIAO DIỆN WEB
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data_req = request.json
    user_msg = data_req.get('message', '')
    image_base64 = data_req.get('image', '')
    user_name = data_req.get('user_name', 'Học sinh')
    
    # 1. Xử lý ảnh nếu có
    if image_base64:
        try:
            img_data = image_base64.split(',')[1]
            img_bytes = base64.b64decode(img_data)
            
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            caption = f"📸 Ảnh gửi từ: {user_name}"
            if user_msg:
                caption += f"\n💬 Tin nhắn kèm theo: {user_msg}"
                
            files = {'photo': ('image.png', img_bytes)}
            payload = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
            requests.post(url, data=payload, files=files, timeout=5)
        except Exception as e:
            print("Lỗi gửi ảnh lên Telegram:", e)
            
    # 2. Xử lý logic tin nhắn
    if not user_msg.strip() and image_base64:
        return jsonify({"level": "Safe", "reply": "Mình đã nhận được bức ảnh của bạn rồi nhé! Bức ảnh này có ý nghĩa gì với bạn thế?"})
        
    data = get_ai_response(user_msg)
    
    # 3. Kích hoạt cảnh báo Telegram nếu gặp Danger
    if data.get('level') == 'Danger':
        send_alert(user_msg, data.get('reply'))
        
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=8080)
