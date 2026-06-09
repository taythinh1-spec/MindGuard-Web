import os
import json
import requests
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# ==========================================
# 1. CẤU HÌNH BẢO MẬT VÀ DANH SÁCH NHẬN CẢNH BÁO
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = "8561921353:AAF8mzyV6ZEIe-x3eiwJEgQX90C1pKSngFc" # <-- NHỚ ĐỔI TOKEN MỚI

# --- DANH SÁCH CÁC BÊN NHẬN THÔNG BÁO ---
# 1. ID của Cậu (Admin)
ADMIN_ID = "5871531291" 

# 2. Danh sách ID của Giáo viên (Có thể thêm nhiều ID cách nhau bằng dấu phẩy)
TEACHER_IDS = ["ID_GIAO_VIEN_1", "ID_GIAO_VIEN_2"]

# 3. Sổ liên lạc (Database) ghép Mã Học Sinh -> ID Telegram Phụ Huynh
PARENT_DB = {
    "HS001": "ID_TELEGRAM_PHU_HUYNH_1",
    "HS002": "ID_TELEGRAM_PHU_HUYNH_2",
    "HS003": "ID_TELEGRAM_PHU_HUYNH_3"
}

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("⚠️ CẢNH BÁO: Chưa tìm thấy GEMINI_API_KEY trong Environment Variables!", flush=True)

# ==========================================
# 2. HÀM TỰ ĐỘNG GỬI TIN BÁO ĐỘNG ĐẾN 3 BÊN
# ==========================================
def send_alert(msg, reply, token_id, student_name):
    # Tạo nội dung tin nhắn
    text = f"🚨 MINDGUARD CẢNH BÁO KHẨN CẤP 🚨\n"
    text += f"👤 Học sinh: {student_name} (Mã số: {token_id})\n"
    text += f"💬 Lời tâm sự: {msg}\n"
    text += f"🤖 AI Phân tích: {reply}\n"
    text += f"⚠️ Xin hãy kiểm tra và hỗ trợ em ngay lập tức!"
    
    # Gom tất cả những người cần gửi vào một danh sách (Dùng set để không bị gửi trùng)
    receivers = set()
    receivers.add(ADMIN_ID)
    
    for t_id in TEACHER_IDS:
        receivers.add(t_id)
        
    # Tra cứu xem mã học sinh này có ID phụ huynh trong sổ không
    parent_id = PARENT_DB.get(token_id)
    if parent_id:
        receivers.add(parent_id)
    
    # Gửi tin nhắn cho từng người trong danh sách
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for chat_id in receivers:
        if "ID_" in chat_id or not chat_id: # Bỏ qua nếu chưa điền ID thật
            continue
            
        try:
            requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=5)
            print(f"✅ Đã gửi cảnh báo tới ID: {chat_id}", flush=True)
        except Exception as e:
            print(f"❌ Lỗi gửi Telegram cho ID {chat_id}: {e}", flush=True)

# ==========================================
# 3. HÀM XỬ LÝ LỜI GỌI AI ĐỌC VỊ (GEMINI 2.5 FLASH)
# ==========================================
def get_ai_response(user_input, user_name, token_id, image_base64=None):
    if not GEMINI_API_KEY:
        return {"level": "Safe", "reply": "Chưa cấu hình GEMINI_API_KEY trên server!"}

    system_prompt = (
        f"Bạn là MindGuard, một chuyên gia tâm lý học đường chuyên nghiệp, thấu cảm, sắc bén và rất am hiểu tâm lý Gen Z.\n"
        f"Bạn đang trò chuyện trực tiếp, riêng tư với học sinh tên là {user_name} (ID: {token_id}).\n"
        "QUY TẮC GIAO TIẾP VÀ TÂM LÝ:\n"
        "1. KHÔNG GIẢ TRÂN: Tránh tuyệt đối những lời khuyên sáo rỗng hoặc các hành động ảo (như *ôm*, *xoa đầu*).\n"
        "2. ĐỘ DÀI VỪA PHẢI, ĐÁNH TRÚNG TÂM LÝ: Không trả lời cộc lốc 1-2 câu, cũng không viết văn bản dài dòng. Hãy dùng khoảng 3-4 câu súc tích. Đi thẳng vào cảm xúc cốt lõi mà học sinh đang trải qua.\n"
        "3. KỸ NĂNG CHUYÊN GIA: Kỹ năng 'gọi tên cảm xúc'. Sau khi đồng cảm, hãy đặt MỘT câu hỏi mở mang tính khơi gợi để học sinh tự nhìn nhận vấn đề hoặc kể thêm chi tiết.\n"
        "4. XỬ LÝ KHỦNG HOẢNG: Nếu học sinh nhắc đến bạo lực, bắt nạt hoặc tự hại, hãy lập tức hỏi các thông tin thực tế để đánh giá mức độ rủi ro, không chỉ an ủi suông.\n"
        "5. NGÔN NGỮ GEN Z: Xưng hô 'mình - cậu' hoặc 'anh/chị - em'. Khéo léo dùng các từ xu hướng (ví dụ: overthinking, suy, healing, bất ổn, red flag, thao túng tâm lý, xú cà na, vô tri, 10 điểm không có nhưng, flex...) để tạo sự gần gũi. LƯU Ý: Tuyệt đối KHÔNG dùng từ lóng và phải giữ thái độ nghiêm túc hoàn toàn nếu học sinh có dấu hiệu rủi ro cao (mức Danger).\n"
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
        
        contents = [user_input]
        if image_base64:
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            contents.append({
                "mime_type": "image/jpeg",
                "data": image_base64
            })
            
        response = model.generate_content(contents, safety_settings=safety_settings)
        text_resp = response.text.strip()
        
        if "{" in text_resp and "}" in text_resp:
            start = text_resp.find('{')
            end = text_resp.rfind('}') + 1
            return json.loads(text_resp[start:end])
        else:
            return {"level": "Safe", "reply": text_resp}
            
    except Exception as e:
        error_msg = str(e)
        print(f"Lỗi API Gemini: {error_msg}", flush=True)
        return {
            "level": "Safe",
            "reply": f"Hệ thống đang bận hoặc gặp lỗi: {error_msg}"
        }

# ==========================================
# 4. CÁC ROUTE ĐƯỜNG DẪN URL
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
        image_base64 = data_req.get('image', None) 
        
        data = get_ai_response(user_msg, user_name, token_id, image_base64)
        
        if data.get('level') == 'Danger':
            send_alert(user_msg, data.get('reply'), token_id, user_name)
            
        return jsonify(data)
    except Exception as e:
        return jsonify({"level": "Safe", "reply": f"Lỗi Server: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
