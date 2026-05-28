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
    print("⚠️ CẢNH BÁO: Chưa tìm thấy GEMINI_API_KEY trong hệ thống!")

# ==========================================
# CƠ SỞ DỮ LIỆU FILE JSON TỰ ĐỘNG
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
        print(f"Lỗi lưu file dữ liệu: {e}")

# Kết nối model AI phù hợp
try:
    valid_models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    chosen_model = 'gemini-1.5-flash' if 'gemini-1.5-flash' in valid_models else valid_models[0]
except Exception:
    chosen_model = 'gemini-1.5-flash'

model = genai.GenerativeModel(chosen_model)
print(f"🧠 MINDGUARD ĐÃ KẾT NỐI VỚI MODEL AI: {chosen_model}")

# ==========================================
# HÀM GỬI CẢNH BÁO TELEGRAM KHẨN CẤP
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
        print(f"Lỗi gửi Telegram ({role}): {e}", flush=True)

# ==========================================
# HÀM GIẢI MÃ SỬA LỖI TRUYỀN ẢNH SANG BYTES
# ==========================================
def parse_base64_image(base64_str):
    try:
        if base64_str and "," in base64_str:
            header, base64_data = base64_str.split(",", 1)
            mime_type = header.split(";")[0].split(":")[1]
            
            # ĐÃ SỬA: Giải mã chính xác chuỗi văn bản Base64 thành dữ liệu Bytes thô để Gemini đọc được ảnh trực tiếp
            img_bytes = base64.b64decode(base64_data)
            
            return {"mime_type": mime_type, "data": img_bytes}
    except Exception as e:
        print(f"Lỗi phân tích Base64 ảnh: {e}")
    return None

# ==========================================
# HÀM XỬ LÝ AI GEMINI ĐỌC VỊ CẢM XÚC SINH TRẮC HỌC
# ==========================================
def get_ai_response(user_input, base64_image=None, is_scan=False):
    system_prompt = (
        "Bạn là MindGuard - Chuyên gia tâm lý học học đường chữa lành tổn thương tinh thần.\n"
        "Hãy lắng nghe thấu cảm sâu sắc, hỗ trợ giảm nhẹ áp lực học tập và cuộc sống.\n"
        "Nhiệm vụ của bạn là phân tích nội dung học sinh cung cấp bao gồm văn bản và hình ảnh.\n\n"
        "ĐẶC BIỆT: Khi học sinh thực hiện Quét Khuôn Mặt bằng camera, hãy đóng vai trò là một máy quét sinh trắc học cảm xúc thông minh. "
        "Hãy quan sát thật kỹ biểu cảm cơ mặt (ánh mắt, nụ cười, chân mày) từ bức ảnh gửi kèm để phân tích bóc tách trạng thái tâm lý thành các chỉ số % rõ ràng "
        "(Ví dụ: Vui vẻ: 20%, Áp lực: 50%, Mệt mỏi: 30%) và lồng ghép các số liệu phần trăm này một cách khéo léo vào câu thoại trò chuyện.\n"
        "Đưa ra lời khuyên chữa lành, thấu cảm sâu sắc dựa trên bức ảnh để giúp học sinh giải tỏa áp lực.\n\n"
        "Sau đó, phân loại tình trạng theo 3 mức độ nguy hiểm:\n"
        "- 'Safe': Trò chuyện thông thường, chia sẻ áp lực nhẹ, hoặc khuôn mặt bình thường/vui vẻ.\n"
        "- 'Warning': Có dấu hiệu khủng hoảng tinh thần nhẹ, khuôn mặt u sầu, kiệt quệ, khóc lóc.\n"
        "- 'Danger': Có ý định làm đau bản thân, tự tử, hoặc hình ảnh thể hiện sự thương tổn nguy hiểm.\n\n"
        "BẮT BUỘC CHỈ TRẢ VỀ ĐÚNG ĐỊNH DẠNG KHỐI JSON, KHÔNG THÊM BẤT KỲ KÝ TỰ HOẶC CHỮ NÀO KHÁC NGOÀI KHỐI JSON NÀY:\n"
        '{"level": "Safe/Warning/Danger", "reply": "Nội dung phản hồi nhẹ nhàng, chữa lành và nhận xét chi tiết tỉ lệ % cảm xúc cơ mặt bằng tiếng Việt"}'
    )
    
    prompt_text = user_input
    if is_scan:
        prompt_text = "Tôi vừa quét biểu cảm khuôn mặt của mình bằng webcam trực tiếp. Hãy phân tích ảnh đi kèm, bóc tách chỉ số % cảm xúc và nói chuyện với tôi nhé."

    contents = [system_prompt, f"Yêu cầu từ học sinh: '{prompt_text}'"]
    
    if base64_image:
        image_part = parse_base64_image(base64_image)
        if image_part:
            contents.append(image_part)

    try:
        response = model.generate_content(contents)
        raw_text = response.text.strip()
        
        # Bóc tách chuỗi JSON đề phòng AI bọc khối code ```json
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_json_str = raw_text[start_idx:end_idx+1]
            return json.loads(clean_json_str)
        else:
            raise Exception("Lỗi định dạng cấu trúc JSON") 
            
    except Exception as e:
        print(f"❌ Lỗi xử lý Gemini API: {e}")
        # Chế độ tự động cứu trợ khẩn cấp dựa trên từ khóa tiêu cực nặng
        danger_keywords = ["tự tử", "chết", "tự sát", "không muốn sống", "tuyệt vọng", "kết thúc", "rạch tay"]
        if any(word in user_input.lower() for word in danger_keywords):
            return {
                "level": "Danger", 
                "reply": "Mình cảm nhận được bạn đang phải chịu đựng áp lực cực kỳ lớn. Hãy dừng lại một chút, mình luôn ở đây lắng nghe bạn. Mình đã gửi tín hiệu hỗ trợ tới thầy cô để đồng hành cùng bạn ngay lúc này. Bạn không cô đơn đâu! ❤️"
            }
        return {"level": "Safe", "reply": "Mình đã nhận được hình ảnh quét của bạn. Nhìn biểu cảm này, hình như bạn đang có khá nhiều suy tư đúng không? Hãy nhắn tin chia sẻ rõ hơn với mình nha! 💙"}

# ==========================================
# CÁC ĐƯỜNG DẪN FLASK ROUTE
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json or {}
        code = data.get('student_code', '').upper().strip()
        name = data.get('student_name', '').strip()
        parent_id = data.get('parent_id', '').strip()

        if not code or not name:
            return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ thông tin!"}), 400

        db = load_db()
        db[code] = {"ten": name, "phu_huynh_id": parent_id if parent_id else None}
        save_db(db)
        return jsonify({"status": "success", "message": "Lưu hồ sơ thành công!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data_req = request.json or {}
        user_msg = data_req.get('message', '')
        student_code = data_req.get('student_code', 'Khách').upper().strip()
        chat_image = data_req.get('image', None)
        is_scan = data_req.get('is_scan', False)
        
        db = load_db()
        student_name = "Học sinh Ẩn danh"
        parent_id = None
        
        if student_code in db:
            student_name = db[student_code]["ten"]
            parent_id = db[student_code]["phu_huynh_id"]
            
        data = get_ai_response(user_msg, base64_image=chat_image, is_scan=is_scan)
        
        # Gửi cảnh báo nếu phát hiện mức độ nguy hiểm (Danger)
        if data.get('level') == 'Danger':
            send_alert(user_msg, data.get('reply'), TEACHER_CHAT_ID, "Giáo viên", student_code, student_name)
            if parent_id:
                send_alert(user_msg, data.get('reply'), parent_id, "Phụ huynh", student_code, student_name)
                
        return jsonify(data)
    except Exception as global_err:
        traceback.print_exc()
        return jsonify({"level": "Safe", "reply": "Hệ thống kết nối AI đang ổn định lại. Bạn quét lại hoặc nhắn tin cho mình nhé!"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
