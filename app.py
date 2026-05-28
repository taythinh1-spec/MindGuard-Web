import os
import json
import base64
import requests
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# ==========================================
# CẤU HÌNH API KEYS VÀ THÔNG TIN BẢO MẬT
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = "8561921353:AAF8mzyV6ZEIe-x3eiwJEgQX90C1pKSngFc"
TEACHER_CHAT_ID = "5871531291"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("⚠️ CẢNH BÁO: Chưa tìm thấy GEMINI_API_KEY trong Environment Variables!", flush=True)

# ==========================================
# HÀM TỰ ĐỘNG GỬI TIN BÁO ĐỘNG ĐẾN TELEGRAM
# ==========================================
def send_alert(msg, reply, chat_id, role, student_code, student_name):
    text = f"🚨 MINDGUARD CẢNH BÁO NGUY HIỂM ({role}) 🚨\n"
    text += f"👤 Học sinh: {student_name} (Mã số: {student_code})\n"
    text += f"💬 Nội dung/Hành vi: {msg if msg else '[Gửi ảnh quét khuôn mặt]'}\n"
    text += f"🤖 Nhận định của Bot: {reply}"
    
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
        print(f"Lỗi giải mã ảnh base64: {e}", flush=True)
    return None

# ==========================================
# HÀM XỬ LÝ LỜI GỌI AI ĐỌC VỊ (GEMINI 2.5)
# ==========================================
def get_ai_response(user_input, base64_image=None, is_scan=False):
    if not GEMINI_API_KEY:
        return {"level": "Safe", "reply": "Chưa cấu hình GEMINI_API_KEY trên server!"}

    system_prompt = (
        "Bạn là MindGuard, chuyên gia phân tích tâm lý học đường qua tin nhắn và biểu cảm khuôn mặt học sinh.\n"
        "Nhiệm vụ: Hãy thấu cảm, đưa ra lời khuyên nhẹ nhàng, đóng vai trò người lắng nghe đáng tin cậy.\n"
        "Đặc biệt nếu nhận diện ảnh, hãy bóc tách ngắn gọn % các cảm xúc (Ví dụ: Vui vẻ: 10%, Lo âu: 60%, Mệt mỏi: 30%).\n"
        "BẮT BUỘC TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON SAU, KHÔNG THÊM CHỮ NÀO KHÁC BÊN NGOÀI:\n"
        '{"level": "Safe/Warning/Danger", "reply": "Nội dung câu trả lời/phân tích tâm lý của bạn tại đây..."}'
    )

    safety_settings = {
        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
    }

    try:
        # Cập nhật chính thức lên dòng Model thế hệ mới 2.5 Flash để loại bỏ lỗi 404 cũ
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_prompt
        )
        
        prompt_text = "Hãy bóc tách % cảm xúc qua biểu cảm khuôn mặt từ bức ảnh chụp thực tế này và trò chuyện với tôi." if is_scan else user_input
        contents = [prompt_text]
        
        if base64_image:
            img_part = parse_base64_image(base64_image)
            if img_part:
                contents.append(img_part)

        response = model.generate_content(contents, safety_settings=safety_settings)
        text_resp = response.text.strip()
        
        # Tiến hành trích xuất chuỗi cấu trúc JSON một cách an toàn
        if "{" in text_resp and "}" in text_resp:
            start = text_resp.find('{')
            end = text_resp.rfind('}') + 1
            return json.loads(text_resp[start:end])
        else:
            return {"level": "Safe", "reply": text_resp}
            
    except Exception as e:
        error_msg = str(e)
        print(f"Lỗi API Gemini: {error_msg}", flush=True)
        
        # Giải quyết dứt điểm lỗi 429 quá tải hạn mức gói free của Google
        if "429" in error_msg or "quota" in error_msg.lower():
            return {
                "level": "Warning",
                "reply": "⏳ MindGuard đang tiếp nhận quá nhiều suy nghĩ của các bạn cùng một lúc! Bạn vui lòng thư giãn và đợi khoảng 1 phút rồi bấm trò chuyện/quét lại với mình nhé! 💙"
            }
            
        return {
            "level": "Safe",
            "reply": f"🚨 Hệ thống Google AI đang bận hoặc gặp lỗi kỹ thuật: {error_msg}"
        }

# ==========================================
# CÁC ROUTE ĐƯỜNG DẪN URL
# ==========================================
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
        
        # Gửi dữ liệu yêu cầu xử lý qua AI
        data = get_ai_response(user_msg, base64_image=chat_image, is_scan=is_scan)
        
        # Nếu AI trả về trạng thái Danger (Nguy hiểm) -> Ngay lập tức gửi cảnh báo về Telegram giáo viên
        if data.get('level') == 'Danger':
            send_alert(user_msg, data.get('reply'), TEACHER_CHAT_ID, "Giáo viên", student_code, "Thịnh")
            
        return jsonify(data)
    except Exception as e:
        return jsonify({"level": "Safe", "reply": f"Lỗi Server xử lý dữ liệu: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
