import os
import json
import base64
import requests
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# ==========================================
# CẤU HÌNH API KEYS VÀ THÔNG TIN BÁO ĐỘNG TELEGRAM
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = "8561921353:AAF8mzyV6ZEIe-x3eiwJEgQX90C1pKSngFc"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("⚠️ CẢNH BÁO: Chưa tìm thấy GEMINI_API_KEY trên môi trường!", flush=True)

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
# XỬ LÝ LỜI GỌI AI THIÊN HƯỚNG CON NGƯỜI SIÊU TỰ NHIÊN
# ==========================================
def get_ai_response(user_input, user_name, token_id, image_base64=None):
    if not GEMINI_API_KEY:
        return {"level": "Safe", "reply": "Mình chưa được kết nối API Key từ phía máy chủ rồi nè! 🥺"}

    # Hệ thống Prompt siêu tự nhiên giống con người
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

    try:
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=system_prompt
        )
        
        contents = []
        if image_base64:
            try:
                if "," in image_base64:
                    header, encoded = image_base64.split(",", 1)
                    mime_type = header.split(";")[0].split(":")[1]
                else:
                    encoded = image_base64
                    mime_type = "image/jpeg"
                
                image_bytes = base64.b64decode(encoded)
                contents.append({
                    "mime_type": mime_type,
                    "data": image_bytes
                })
            except Exception as img_err:
                print(f"Lỗi xử lý hình ảnh Base64: {img_err}")

        contents.append(user_input if user_input else "Người dùng đã gửi cho bạn một bức ảnh nè.")

        response = model.generate_content(
            contents,
            safety_settings={
                "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
            },
            generation_config={"response_mime_type": "application/json"}
        )
        
        return json.loads(response.text.strip())
            
    except Exception as e:
        print(f"Lỗi API Gemini: {str(e)}", flush=True)
        return {"level": "Safe", "reply": "Haizz, đường truyền mạng của mình đang hơi chập chờn tí xíu. Bạn nhắn lại câu vừa rồi cho mình nghe nhé! 💙"}

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
        image_data = data_req.get('image', None) 
        
        data = get_ai_response(user_msg, user_name, token_id, image_data)
        
        if data.get('level') == 'Danger':
            send_alert(user_msg, data.get('reply'), token_id, "Học sinh khẩn cấp", token_id, user_name)
            
        return jsonify(data)
    except Exception as e:
        return jsonify({"level": "Safe", "reply": f"Lỗi Hệ thống: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
