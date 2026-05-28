import os
import json
import base64
import requests
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# ==========================================
# CẤU HÌNH API KEYS VÀ BẢO MẬT
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = "8561921353:AAF8mzyV6ZEIe-x3eiwJEgQX90C1pKSngFc"
TEACHER_CHAT_ID = "5871531291"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("⚠️ CẢNH BÁO: Chưa tìm thấy GEMINI_API_KEY!")

# ==========================================
# HÀM GỬI CẢNH BÁO TELEGRAM
# ==========================================
def send_alert(msg, reply, chat_id, role, student_code, student_name):
    text = f"🚨 MINDGUARD CẢNH BÁO ({role}) 🚨\n"
    text += f"👤 Học sinh: {student_name} (Mã: {student_code})\n"
    text += f"💬 Tin nhắn: {msg}\n"
    text += f"🤖 Bot phản hồi: {reply}"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=5)
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}", flush=True)

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
    if not GEMINI_API_KEY:
        return {"level": "Safe", "reply": "Chưa cấu hình GEMINI_API_KEY trên server!"}

    system_prompt = (
        "Bạn là MindGuard, chuyên gia phân tích tâm lý qua khuôn mặt.\n"
        "BẮT BUỘC: Nhìn ảnh và bóc tách thành các chỉ số %. VD: Vui vẻ: 20%, Áp lực: 50%, Mệt mỏi: 30%.\n"
        "Sau đó phân tích thấu cảm.\n"
        "TRẢ VỀ ĐÚNG CHUỖI JSON SAU:\n"
        '{"level": "Safe/Warning/Danger", "reply": "Câu trả lời của bạn ở đây..."}'
    )

    # ĐỊNH DẠNG DICTIONARY CHUẨN: Giữ kết nối ở cổng v1 Stable, không bị tụt về v1beta
    safety_settings = {
        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
    }

    try:
        # Khởi tạo model kèm system_instruction theo đúng chuẩn tài liệu Google AI mới nhất
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=system_prompt
        )
        
        prompt_text = "Hãy bóc tách % cảm xúc từ ảnh này và nói chuyện với tôi." if is_scan else user_input
        contents = [prompt_text]
        
        if base64_image:
            img_part = parse_base64_image(base64_image)
            if img_part:
                contents.append(img_part)

        response = model.generate_content(contents, safety_settings=safety_settings)
        text_resp = response.text.strip()
        
        # Bắt và bóc tách chuỗi JSON từ phản hồi của AI
        if "{" in text_resp and "}" in text_resp:
            start = text_resp.find('{')
            end = text_resp.rfind('}') + 1
            return json.loads(text_resp[start:end])
        else:
            return {"level": "Safe", "reply": text_resp}
            
    except Exception as e:
        print(f"Lỗi API: {e}")
        return {
            "level": "Safe",
            "reply": f"🚨 Hệ thống báo lỗi từ Google: {str(e)}"
        }

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data_req = request.json or {}
        user_msg = data_req.get('message', '')
        student_code = data_req.get('student_code', 'HS001').upper().strip()
        chat_image = data_req.get('image', None)
        is_scan = data_req.get('is_scan', False)
        
        # Gọi AI lấy kết quả phân tích
        data = get_ai_response(user_msg, base64_image=chat_image, is_scan=is_scan)
        
        # KÍCH HOẠT TELEGRAM NẾU AI ĐÁNH GIÁ LÀ NGUY HIỂM (Danger)
        if data.get('level') == 'Danger':
            send_alert(user_msg, data.get('reply'), TEACHER_CHAT_ID, "Giáo viên", student_code, "Thịnh")
            
        return jsonify(data)
    except Exception as e:
        return jsonify({"level": "Safe", "reply": f"Lỗi Server: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
