import os
import json
import base64
import requests
import traceback
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# ==========================================
# CẤU HÌNH API KEYS
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
TELEGRAM_TOKEN = "8561921353:AAF8mzyV6ZEIe-x3eiwJEgQX90C1pKSngFc"
TEACHER_CHAT_ID = "5871531291"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("⚠️ CẢNH BÁO: Chưa tìm thấy GEMINI_API_KEY!")

try:
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    model = None

def parse_base64_image(base64_str):
    try:
        if base64_str and "," in base64_str:
            header, base64_data = base64_str.split(",", 1)
            mime_type = header.split(";")[0].split(":")[1]
            img_bytes = base64.b64decode(base64_data)
            return {"mime_type": mime_type, "data": img_bytes}
    except Exception as e:
        print(f"Lỗi giải mã ảnh: {e}")
    return None

def get_ai_response(user_input, base64_image=None, is_scan=False):
    if not GEMINI_API_KEY or not model:
        return {"level": "Safe", "reply": "Chưa có GEMINI_API_KEY trên Render!"}

    system_prompt = (
        "Bạn là chuyên gia phân tích tâm lý qua khuôn mặt.\n"
        "BẮT BUỘC: Nhìn ảnh và bóc tách thành các chỉ số %. VD: Vui vẻ: 20%, Áp lực: 50%, Mệt mỏi: 30%.\n"
        "Sau đó phân tích thấu cảm.\n"
        "TRẢ VỀ ĐÚNG CHUỖI JSON SAU:\n"
        '{"level": "Safe", "reply": "Câu trả lời của bạn ở đây..."}'
    )

    prompt_text = "Hãy bóc tách % cảm xúc từ ảnh này và nói chuyện với tôi." if is_scan else user_input
    contents = [system_prompt, prompt_text]
    
    if base64_image:
        img_part = parse_base64_image(base64_image)
        if img_part:
            contents.append(img_part)

    try:
        # Tắt toàn bộ bộ lọc an toàn để Google không chặn ảnh khuôn mặt
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
        
        response = model.generate_content(contents, safety_settings=safety_settings)
        text_resp = response.text.strip()
        
        # Trích xuất JSON an toàn
        if "{" in text_resp and "}" in text_resp:
            start = text_resp.find('{')
            end = text_resp.rfind('}') + 1
            return json.loads(text_resp[start:end])
        else:
            return {"level": "Safe", "reply": text_resp}
            
    except Exception as e:
        # NẾU CÓ LỖI, IN THẲNG RA MÀN HÌNH ĐỂ BẮT BỆNH
        print(f"Lỗi API: {e}")
        return {
            "level": "Safe",
            "reply": f"🚨 Hệ thống báo lỗi: {str(e)}. Bạn hãy chụp lỗi này lại nhé!"
        }

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data_req = request.json or {}
        user_msg = data_req.get('message', '')
        chat_image = data_req.get('image', None)
        is_scan = data_req.get('is_scan', False)
        
        data = get_ai_response(user_msg, base64_image=chat_image, is_scan=is_scan)
        return jsonify(data)
    except Exception as e:
        return jsonify({"level": "Safe", "reply": f"Lỗi Web: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
