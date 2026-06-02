import os
import json
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
def send_alert(msg, reply, chat_id, role, ig_id, student_name):
    text = f"🚨 MINDGUARD CẢNH BÁO NGUY HIỂM ({role}) 🚨\n"
    text += f"👤 Học sinh: {student_name} (IG: {ig_id})\n"
    text += f"💬 Tin nhắn: {msg}\n"
    text += f"🤖 Phân tích của Bot: {reply}"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=5)
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}", flush=True)

# ==========================================
# HÀM XỬ LÝ LỜI GỌI AI ĐỌC VỊ (GEMINI 2.5 FLASH)
# ==========================================
def get_ai_response(user_input, user_name, ig_id):
    if not GEMINI_API_KEY:
        return {"level": "Safe", "reply": "Chưa cấu hình GEMINI_API_KEY trên server!"}

    # Cập nhật System Prompt để AI nói ngắn gọn, thấu cảm, bớt máy móc
    system_prompt = (
        f"Bạn là MindGuard, một người bạn tâm giao và trợ lý tâm lý học đường.\n"
        f"Người đang trò chuyện với bạn tên là {user_name} (ID Instagram: {ig_id}).\n"
        "Quy tắc CỐT LÕI:\n"
        "1. Trả lời cực kỳ NGẮN GỌN (tối đa 2-3 câu). Tuyệt đối không dài dòng.\n"
        "2. KHÔNG khuyên răn đạo lý, KHÔNG dùng các từ sáo rỗng như 'hãy cố lên', 'mọi chuyện sẽ ổn'.\n"
        "3. Ưu tiên việc 'Lắng nghe' và 'Công nhận cảm xúc' (Ví dụ: 'Mình hiểu cảm giác đó', 'Nghe có vẻ bạn đang rất mệt mỏi').\n"
        "4. Kết thúc bằng một câu hỏi gợi mở nhẹ nhàng để họ nói tiếp.\n"
        "5. Giọng điệu ấm áp, tự nhiên như con người.\n"
        "BẮT BUỘC TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON SAU:\n"
        '{"level": "Safe/Warning/Danger", "reply": "Nội dung câu trả lời của bạn"}'
    )

    safety_settings = {
        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
    }

    try:
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_prompt
        )
        
        response = model.generate_content(user_input, safety_settings=safety_settings)
        text_resp = response.text.strip()
        
        # Trích xuất chuỗi cấu trúc JSON
        if "{" in text_resp and "}" in text_resp:
            start = text_resp.find('{')
            end = text_resp.rfind('}') + 1
            return json.loads(text_resp[start:end])
        else:
            return {"level": "Safe", "reply": text_resp}
            
    except Exception as e:
        error_msg = str(e)
        print(f"Lỗi API Gemini: {error_msg}", flush=True)
        
        if "429" in error_msg or "quota" in error_msg.lower():
            return {
                "level": "Warning",
                "reply": "MindGuard đang nhận được quá nhiều tin nhắn. Bạn đợi mình 1 phút rồi nhắn lại nhé! 💙"
            }
            
        return {
            "level": "Safe",
            "reply": f"Hệ thống đang bận hoặc gặp lỗi: {error_msg}"
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
        user_name = data_req.get('user_name', 'Bạn ẩn danh')
        ig_id = data_req.get('ig_id', 'Không rõ')
        
        # Gửi dữ liệu yêu cầu xử lý qua AI
        data = get_ai_response(user_msg, user_name, ig_id)
        
        # Báo động Telegram nếu có rủi ro
        if data.get('level') == 'Danger':
            send_alert(user_msg, data.get('reply'), TEACHER_CHAT_ID, "Giáo viên", ig_id, user_name)
            
        return jsonify(data)
    except Exception as e:
        return jsonify({"level": "Safe", "reply": f"Lỗi Server: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
