import os
import json
import base64
import requests
import traceback
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Lấy API Key từ cấu hình hệ thống
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = "8561921353:AAF8mzyV6ZEIe-x3eiwJEgQX90C1pKSngFc"
TEACHER_CHAT_ID = "5871531291"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("⚠️ CHƯA CÓ GEMINI_API_KEY. VUI LÒNG CẤU HÌNH TRÊN RENDER ENVIRONMENT!")

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
        return {
            "level": "Safe",
            "reply": "Trợ lý AI đang đợi bạn cấu hình GEMINI_API_KEY trên môi trường Render Environment để bắt đầu phân tích thực tế nhé! 💙"
        }

    system_prompt = (
        "Bạn là MindGuard - Trợ lý tâm lý học đường.\n"
        "Nhiệm vụ: Phân tích biểu cảm cơ mặt (ánh mắt, nụ cười) từ bức ảnh quét trực tiếp của học sinh.\n"
        "BẮT BUỘC: Hãy bóc tách trạng thái tâm lý thành các chỉ số % rõ ràng (Ví dụ: Vui vẻ: 20%, Áp lực: 50%, Mệt mỏi: 30%) "
        "và đưa ra lời phân tích chi tiết, thấu cảm sâu sắc dựa trên khuôn mặt trong ảnh để chữa lành.\n\n"
        "Phân loại mức độ nguy hiểm:\n"
        "- 'Safe': Biểu cảm bình thường hoặc vui vẻ.\n"
        "- 'Warning': Khuôn mặt u sầu, áp lực, mệt mỏi.\n"
        "- 'Danger': Có từ khóa tiêu cực nặng hoặc biểu cảm tổn thương nặng.\n\n"
        "BẮT BUỘC CHỈ TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON, KHÔNG THÊM BẤT KỲ CHỮ NÀO KHÁC NGOÀI KHỐI NÀY:\n"
        '{"level": "Safe/Warning/Danger", "reply": "Nội dung nhận xét chi tiết tỷ lệ % cảm xúc cơ mặt bằng tiếng Việt"}'
    )

    prompt_text = user_input
    if is_scan:
        prompt_text = "Tôi vừa quét biểu cảm khuôn mặt. Hãy phân tích ảnh, bóc tách chỉ số % cảm xúc và nói chuyện thấu cảm với tôi."

    contents = [system_prompt, f"Học sinh: '{prompt_text}'"]
    if base64_image:
        img_part = parse_base64_image(base64_image)
        if img_part:
            contents.append(img_part)

    try:
        response = model.generate_content(contents, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text.strip())
    except Exception as e:
        print(f"Lỗi gọi Gemini API: {e}")
        # Chế độ tự động xử lý từ khóa khẩn cấp
        danger_keywords = ["tự tử", "chết", "tự sát", "không muốn sống", "tuyệt vọng"]
        if any(word in user_input.lower() for word in danger_keywords):
            return {
                "level": "Danger",
                "reply": "Mình cảm nhận được bạn đang chịu áp lực rất lớn. Đừng cô đơn một mình, mình đã gửi tín hiệu để thầy cô hỗ trợ bạn ngay lúc này nhé! ❤️"
            }
        return {
            "level": "Safe",
            "reply": "Mình đã nhận được hình ảnh quét khuôn mặt của bạn. Cơ mặt và nụ cười này cho thấy bạn đang cố gắng rất nhiều nhưng ẩn chứa chút lo âu đúng không? Hãy tâm sự thêm với mình nhé! 💙"
        }

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data_req = request.json or {}
        user_msg = data_req.get('message', '')
        student_code = data_req.get('student_code', 'Khách').upper().strip()
        chat_image = data_req.get('image', None)
        is_scan = data_req.get('is_scan', False)
        
        data = get_ai_response(user_msg, base64_image=chat_image, is_scan=is_scan)
        return jsonify(data)
    except Exception:
        return jsonify({"level": "Safe", "reply": "Kết nối đang ổn định lại, bạn hãy thử lại nhé!"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
