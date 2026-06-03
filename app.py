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

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("⚠️ CẢNH BÁO: Chưa tìm thấy GEMINI_API_KEY trong Environment Variables!", flush=True)

# ==========================================
# HÀM TỰ ĐỘNG GỬI TIN BÁO ĐỘNG ĐẾN TELEGRAM
# ==========================================
def send_alert(msg, reply, chat_id, role, token_id, student_name):
    text = f"🚨 MINDGUARD CẢNH BÁO NGUY HIỂM ({role}) 🚨\n"
    text += f"👤 Học sinh: {student_name} (Mã Chat ID: {token_id})\n"
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
# [ĐÃ SỬA]: Thêm tham số image_base64 để nhận ảnh
def get_ai_response(user_input, user_name, token_id, image_base64=None):
    if not GEMINI_API_KEY:
        return {"level": "Safe", "reply": "Chưa cấu hình GEMINI_API_KEY trên server!"}

    # [ĐÃ SỬA]: Tinh chỉnh System Prompt để Mascot thân thiện, cảm xúc và giống người hơn
    system_prompt = (
        f"Bạn là MindGuard, một người bạn tâm giao, tri kỷ tuổi teen vô cùng ấm áp, tinh tế.\n"
        f"Người đang trút bầu tâm sự với bạn tên là {user_name} (Mã Token ID: {token_id}).\n\n"
        "QUY TẮC NGÔN NGỮ GIỐNG CON NGƯỜI 100%:\n"
        "1. KHÔNG DÙNG VĂN ROBOT: Tuyệt đối không nói các câu rập khuôn như 'Tôi hiểu cảm giác của bạn', 'Tôi có thể giúp gì', 'Chào bạn'.\n"
        "2. TỪ NGỮ CẢM THÁN & COLLOQUIALISMS: Hãy bắt đầu câu bằng các từ ngữ biểu lộ cảm xúc thật của con người tùy theo hoàn cảnh như: 'Haizz...', 'Ui...', 'Thương bạn ghê...', 'Gì chứ...', 'Ôi trời...'. Sử dụng các đuôi từ thân mật: 'nè', 'nha', 'đó', 'ơi', 'á'.\n"
        "3. ĐỒNG CẢM SÂU SẮC TRƯỚC: Nếu họ buồn/áp lực, hãy ôm họ bằng lời nói trước (Ví dụ: 'Nghe xót xa thế...', 'Nghe là biết bạn đã mệt mỏi thế nào rồi...', 'Đến đây mình ôm một cái thật chặt nè...'). Không khuyên răn đạo lý, không dạy đời.\n"
        "4. SIÊU NGẮN GỌN VÀ GỢI MỞ: Trả lời tối đa từ 2 đến 3 câu ngắn. Hãy kết thúc bằng một câu hỏi quan tâm, rủ rê dịu dàng (Ví dụ: 'Giờ có chuyện gì làm bạn thấy dễ chịu nhất không?', 'Kể thêm cho mình nghe đi, mình vẫn ngồi đây nghe bạn mà...').\n"
        "5. PHÂN TÍCH ẢNH THÂN THIỆN: Nếu họ gửi ảnh kèm theo, hãy chú ý chi tiết trong ảnh và bình luận một cách tự nhiên như một người bạn xem ảnh qua mạng.\n\n"
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
        
        # [ĐÃ SỬA]: Xử lý đưa cả text và ảnh vào AI
        contents = [user_input]
        if image_base64:
            # Lọc bỏ phần tiền tố header của base64 nếu có (ví dụ: data:image/png;base64,...)
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            contents.append({
                "mime_type": "image/jpeg", # Dùng chung jpeg/png đều được
                "data": image_base64
            })
            
        response = model.generate_content(contents, safety_settings=safety_settings)
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
        token_id = data_req.get('token_id', '000000') 
        
        # [ĐÃ SỬA]: Lấy thêm biến ảnh từ Frontend gửi lên
        image_base64 = data_req.get('image', None) 
        
        data = get_ai_response(user_msg, user_name, token_id, image_base64)
        
        # Gửi cảnh báo trực tiếp về mã token_id (Chat ID Telegram) mà người dùng đã nhập
        if data.get('level') == 'Danger':
            send_alert(user_msg, data.get('reply'), token_id, "Người dùng/Giáo viên", token_id, user_name)
            
        return jsonify(data)
    except Exception as e:
        return jsonify({"level": "Safe", "reply": f"Lỗi Server: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
