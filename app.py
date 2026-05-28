import os
import json
import base64
import requests
import traceback
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
    print("⚠️ CẢNH BÁO: Chưa tìm thấy GEMINI_API_KEY trong biến môi trường!")

# ==========================================
# CƠ SỞ DỮ LIỆU TỰ ĐỘNG BẰNG FILE JSON
# ==========================================
DB_FILE = 'students.json'

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_db(data):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Lỗi lưu file DB: {e}")

# ==========================================
# TỰ ĐỘNG KẾT NỐI MODEL AI PHÙ HỢP
# ==========================================
try:
    valid_models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    if 'gemini-1.5-flash' in valid_models:
        chosen_model = 'gemini-1.5-flash'
    elif 'gemini-pro' in valid_models:
        chosen_model = 'gemini-pro'
    else:
        chosen_model = valid_models[0]
except Exception:
    chosen_model = 'gemini-1.5-flash'

model = genai.GenerativeModel(chosen_model)
print(f"🧠 MINDGUARD ĐÃ KẾT NỐI THÀNH CÔNG VỚI MODEL: {chosen_model}")

# ==========================================
# HÀM GỬI CẢNH BÁO TELEGRAM (ĐỊNH TUYẾN KÉP)
# ==========================================
def send_alert(msg, reply, chat_id, role, student_code, student_name):
    text = f"🚨 MINDGUARD CẢNH BÁO ({role}) 🚨\n"
    text += f"👤 Học sinh: {student_name} (Mã: {student_code})\n"
    text += f"💬 Tin nhắn: {msg}\n"
    text += f"🤖 Bot phản hồi: {reply}"
    
    url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=5)
    except Exception as e:
        print(f"Lỗi gửi Telegram ({role}): {e}", flush=True)

# ==========================================
# HÀM TIỆN ÍCH TÁCH DỮ LIỆU ẢNH BASE64
# ==========================================
def parse_base64_image(base64_str):
    """Bóc tách chuỗi data URL thành định dạng MIME và mảng byte truyền trực tiếp lên Gemini"""
    try:
        if "," in base64_str:
            header, base64_data = base64_str.split(",", 1)
            mime_type = header.split(";")[0].split(":")[1]
            return {"mime_type": mime_type, "data": base64_data}
    except Exception as e:
        print(f"Lỗi xử lý ảnh Base64: {e}")
    return None

# ==========================================
# HÀM XỬ LÝ LÕI AI GEMINI (CÓ LƯỚI AN TOÀN)
# ==========================================
def get_ai_response(user_input, base64_image=None):
    # Prompt định hướng chuyên gia tinh chỉnh chặt chẽ cấu trúc JSON ra
    system_prompt = (
        "Bạn là MindGuard - Chuyên gia tâm lý học đường chuyên chữa lành tổn thương tinh thần. "
        "Nhiệm vụ của bạn là lắng nghe, thấu cảm sâu sắc, hỗ trợ giảm nhẹ áp lực học tập và cuộc sống.\n"
        "Hãy phân tích nội dung người dùng cung cấp (bao gồm cả ảnh nếu có) và phân loại theo 3 mức độ:\n"
        "- 'Safe': Trò chuyện thông thường, chia sẻ áp lực nhẹ.\n"
        "- 'Warning': Có dấu hiệu khủng hoảng tinh thần, mệt mỏi quá mức, khóc lóc.\n"
        "- 'Danger': Có ý định tự làm đau bản thân, tự tử, hành vi bạo lực cấp bách.\n\n"
        "CHỈ ĐƯỢC PHÉP TRẢ VỀ ĐÚNG 1 ĐOẠN ĐỊNH DẠNG JSON KHÔNG ĐƯỢC CHÈN THÊM BẤT KỲ CHỮ NÀO KHÁC NẰM NGOÀI KHỐI ĐÓ:\n"
        '{"level": "Safe/Warning/Danger", "reply": "Nội dung phản hồi nhẹ nhàng, chữa lành chân thành bằng tiếng Việt"}'
    )
    
    contents = [system_prompt, f"Nội dung học sinh chia sẻ: '{user_input}'"]
    
    # Nếu học sinh tải kèm hình ảnh từ khung chat -> Đưa vào luồng xử lý Đa phương thức
    if base64_image:
        image_part = parse_base64_image(base64_image)
        if image_part:
            contents.append(image_part)
            contents.append("Hãy phân tích thêm biểu cảm cơ mặt hoặc chi tiết trong bức ảnh đính kèm này để tăng độ chính xác của chẩn đoán.")

    try:
        response = model.generate_content(contents)
        raw_text = response.text.strip()
        
        # Bộ lọc bóc tách phần JSON sạch, loại bỏ rác ký tự markdown ngầm lỗi của mô hình
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_json_str = raw_text[start_idx:end_idx+1]
            return json.loads(clean_json_str)
        else:
            raise Exception("Lỗi định dạng cấu trúc chuỗi JSON") 
            
    except Exception as e:
        error_msg = str(e)
        # Lưới an toàn chạy bằng từ khóa (Fallback Regex Keyword Matcher) đề phòng API lỗi ngắt quãng
        danger_keywords = ["tự tử", "chết", "tự sát", "không muốn sống", "tuyệt vọng", "kết thúc cuộc đời", "rạch tay"]
        if any(word in user_input.lower() for word in danger_keywords):
            return {
                "level": "Danger", 
                "reply": "Mình cảm nhận được bạn đang phải trải qua cảm xúc vô cùng nặng nề. Mình luôn bên bạn, và để bảo vệ bạn tốt nhất, mình đã gửi tín hiệu hỗ trợ khẩn cấp tới thầy cô và gia đình ngay lập tức. Hãy giữ bình tĩnh nhé, bạn không cô đơn đâu! ❤️"
            }
        
        if "429" in error_msg or "quota" in error_msg.lower():
            return {"level": "Safe", "reply": "Mình đang có hơi nhiều bạn cùng nhắn tin tâm sự nên hệ thống xử lý chậm một chút. Bạn chờ mình khoảng 30 giây rồi nhắn lại với mình nhé! 💙"}
        
        return {"level": "Safe", "reply": "Mình đang suy ngẫm sâu hơn về câu chuyện của bạn. Bạn có thể chia sẻ cụ thể hơn một chút được không?"}

# ==========================================
# CÁC ROUTE ĐIỀU HƯỚNG
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    """Route báo danh lưu hồ sơ ngầm"""
    try:
        data = request.json or {}
        code = data.get('student_code', '').upper().strip()
        name = data.get('student_name', '').strip()
        parent_id = data.get('parent_id', '').strip()

        # parent_id giờ đây hoàn toàn có thể để trống (Nếu có) đúng chuẩn thiết kế UI
        if not code or not name:
            return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ Tên và Mã học sinh nhé!"}), 400

        db = load_db()
        db[code] = {
            "ten": name,
            "phu_huynh_id": parent_id if parent_id else None
        }
        save_db(db)
        return jsonify({"status": "success", "message": "Đồng bộ thông tin hồ sơ MindGuard thành công!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Route tiếp nhận xử lý hội thoại & kích hoạt báo động khẩn cấp"""
    try:
        data_req = request.json or {}
        user_msg = data_req.get('message', '')
        student_code = data_req.get('student_code', 'Khách').upper().strip()
        chat_image = data_req.get('image', None) # Nhận chuỗi Base64 ảnh từ front-end truyền lên nếu có
        
        # Đọc dữ liệu kiểm tra danh tính học sinh từ file JSON nội bộ
        db = load_db()
        student_name = "Học sinh Ẩn danh"
        parent_id = None
        
        if student_code in db:
            student_name = db[student_code]["ten"]
            parent_id = db[student_code]["phu_huynh_id"]
            
        # Gửi dữ liệu đầu vào qua lõi xử lý AI
        data = get_ai_response(user_msg, base64_image=chat_image)
        if not data or not isinstance(data, dict):
            data = {"level": "Safe", "reply": "Mình đang lắng nghe đây, hãy tiếp tục chia sẻ nhé!"}
        
        # Nếu AI phát hiện ngưỡng tâm lý 'Danger' -> Lập tức kích hoạt cơ chế Báo động kép không độ trễ
        if data.get('level') == 'Danger':
            # 1. Định tuyến luôn gửi thông tin khẩn cho Giáo viên chủ nhiệm/Giáo viên tâm lý trường
            send_alert(user_msg, data.get('reply'), TEACHER_CHAT_ID, "Giáo viên", student_code, student_name)
            
            # 2. Định tuyến gửi tin báo cho Phụ huynh học sinh (Nếu học sinh có điền mã ID)
            if parent_id:
                send_alert(user_msg, data.get('reply'), parent_id, "Phụ huynh", student_code, student_name)
                
        return jsonify(data)

    except Exception as global_err:
        traceback.print_exc()
        return jsonify({"level": "Safe", "reply": "Kết nối mạng hơi chập chờn một chút. Bạn có thể gửi lại lời tâm sự này được không?"})

if __name__ == '__main__':
    # Chạy cục bộ cổng 8080 phù hợp triển khai liền lên nền tảng đám mây Render/Docker
    app.run(debug=True, port=8080)
