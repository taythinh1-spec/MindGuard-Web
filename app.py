# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import json
import traceback
import requests
import base64  # Thêm thư viện này để xử lý ảnh mã hóa từ giao diện web

app = Flask(__name__)

# ==========================================
# GIỮ NGUYÊN 100% THÔNG TIN API KEYS TỪ ẢNH CỦA BẠN
# ==========================================
GEMINI_API_KEY = "AIzaSyCoZZkAzWZiB9ftuOQSlKJbkPXct2cExzc"
TELEGRAM_TOKEN = "7061902150:AAFnEcywGZc-z6inJKgQX6bCIpk5ngFc"
TELEGRAM_CHAT_ID = "5871331291"

genai.configure(api_key=GEMINI_API_KEY)

# Tự động kết nối Model AI (Giữ nguyên logic cũ của bạn)
valid_models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
if 'gemini-1.5-flash' in valid_models:
    chosen_model = 'gemini-1.5-flash'
elif 'gemini-pro' in valid_models:
    chosen_model = 'gemini-pro'
else:
    chosen_model = valid_models[0]

model = genai.GenerativeModel(chosen_model)
print(f"🧠 MINDGUARD ĐÃ KẾT NỐI VỚI MODEL: {chosen_model}")

def send_alert(msg, reply):
    """Giữ nguyên hàm gửi cảnh báo chữ khi gặp Danger của bạn"""
    text = f"🚨 CẢNH BÁO MỨC ĐỘ NGUY HIỂM!\nHọc sinh: {msg}\nBot: {reply}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
    except:
        pass

def get_ai_response(user_input):
    """Giữ nguyên hàm bóc tách dữ liệu AI Gemini của bạn"""
    prompt = (
        f"Bạn là chuyên gia tâm lý MindGuard AI. Hãy phản hồi: '{user_input}'. "
        "Yêu cầu trả về duy nhất định dạng JSON: "
        '{"Level": "Safe/Warning/Danger", "reply": "Nội dung"}'
    )
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        clean_json = raw_text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"Level": "Error", "reply": "Hệ thống đang bận, mình sẽ quay lại ngay!"}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    # Lấy dữ liệu từ giao diện Web gửi lên
    data_req = request.json
    user_msg = data_req.get('message', '')
    image_base64 = data_req.get('image', '')  # Nhận ảnh từ nút bấm trên giao diện
    user_name = data_req.get('user_name', 'Học sinh')

    # 1. NẾU HỌC SINH CÓ TẢI ẢNH -> TỰ ĐỘNG GỬI ẢNH ĐÓ VỀ TELEGRAM CHO BẠN XEM
    if image_base64:
        try:
            # Giải mã chuỗi ảnh Base64
            img_data = image_base64.split(',')[1]
            img_bytes = base64.b64decode(img_data)
            
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            caption = f"📸 Bức ảnh gửi từ: {user_name}"
            if user_msg:
                caption += f"\n💬 Lời nhắn kèm theo: {user_msg}"
                
            files = {'photo': ('image.png', img_bytes)}
            payload = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
            requests.post(url, data=payload, files=files, timeout=5)
        except Exception as e:
            print("Lỗi gửi ảnh lên Telegram:", e)

    # 2. XỬ LÝ AI GEMINI CHO TIN NHẮN (Giống hệt logic cũ của bạn)
    # Trường hợp học sinh chỉ gửi ảnh và để trống ô chữ
    if not user_msg.strip() and image_base64:
        return jsonify({"Level": "Safe", "reply": "Mình đã nhận được bức ảnh của bạn rồi nhé! Bức ảnh này có ý nghĩa gì với bạn thế?"})

    # Nếu có chữ, đưa cho AI phân tích tâm lý
    data = get_ai_response(user_msg)
    
    # Nếu AI đánh giá Danger -> Kích hoạt gửi tin nhắn cảnh báo về Telegram
    if data.get('Level') == 'Danger':
        send_alert(user_msg, data.get('reply'))
        
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
