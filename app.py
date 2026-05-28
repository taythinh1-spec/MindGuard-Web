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
        print(f"Lỗi lưu file dữ liệu: {e}")

# Kết nối model AI
try:
    valid_models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    chosen_model = 'gemini-1.5-flash' if 'gemini-1.5-flash' in valid_models else valid_models[0]
except Exception:
    chosen_model = 'gemini-1.5-flash'

model = genai.GenerativeModel(chosen_model)
print(f"🧠 MINDGUARD ĐÃ KẾT NỐI VỚI MODEL CAMERA: {chosen_model}")

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
        print(f"Lỗi gửi Telegram ({role}): {e}", flush=True)

def parse_base64_image(base64_str):
    try:
        if base64_str and "," in base64_str:
            header, base64_data = base64_str.split(",", 1)
            mime_type = header.split(";")[0].split(":")[1]
            return {"mime_type": mime_type, "data": base64_data}
    except Exception as e:
        print(f"Lỗi phân tích Base64 ảnh: {e}")
    return None

# ==========================================
# HÀM XỬ LÝ LÕI AI GEMINI (ĐÃ TỐI ƯU CHO CHỨC NĂNG QUÉT FACE)
# ==========================================
def get_ai_response(user_input, base64_image=None):
    system_prompt = (
        "Bạn là MindGuard - Chuyên gia tâm lý học đường chữa lành tổn thương tinh thần.\n"
        "Hãy lắng nghe thấu cảm sâu sắc, hỗ trợ giảm nhẹ áp lực học tập và cuộc sống.\n"
        "Nhiệm vụ của bạn là phân tích nội dung học sinh cung cấp bao gồm văn bản và hình ảnh.\n"
        "ĐẶC BIỆT: Nếu có hình ảnh khuôn mặt gửi kèm từ webcam, hãy đóng vai trò như một máy quét cảm xúc thông minh. "
        "Hãy nhìn kỹ biểu cảm (mắt, miệng, cơ mặt, cử chỉ) để đoán xem bạn ấy đang vui, buồn, mệt mỏi, áp lực hay bất an và đưa ra lời nhận xét thấu cảm chân thành nhất.\n\n"
        "Sau đó, phân loại tình trạng theo 3 mức độ:\n"
        "- 'Safe': Trò chuyện thông thường, chia sẻ áp lực nhẹ, hoặc khuôn mặt bình thường/vui vẻ.\n"
        "- 'Warning': Có dấu hiệu khủng hoảng tinh thần, khuôn mặt u sầu, kiệt quệ, khóc lóc.\n"
        "- 'Danger': Có ý định làm đau bản thân, tự tử, hoặc hình ảnh thể hiện sự thương tổn nguy hiểm.\n\n"
        "BẮT BUỘC CHỈ TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON, KHÔNG THÊM BẤT KỲ CHỮ NÀO KHÁC NGOÀI KHỐI JSON NÀY:\n"
        '{"level": "Safe/Warning/Danger", "reply": "Nội dung phản hồi nhẹ nhàng, phân tích biểu cảm và chữa lành chân thành bằng tiếng Việt"}'
    )
    
    # Điều chỉnh câu lệnh nếu đây là ảnh quét trực tiếp từ hệ thống webcam
    prompt_text = user_input
    if "[Hệ thống]" in user_input:
        prompt_text = "Tôi vừa thực hiện quét khuôn mặt của mình bằng webcam trực tiếp. Hãy phân tích biểu cảm của tôi qua bức ảnh đi kèm này và trò chuyện với tôi nhé."

    contents = [system_prompt, f"Yêu cầu từ học sinh: '{prompt_text}'"]
    
    if base64_image:
        image_part = parse_base64_image(base64_image)
        if image_part:
            contents.append(image_part)

    try:
        response = model.generate_content(contents)
        raw_text = response.text.strip()
        
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_json_str = raw_text[start_idx:end_idx+1]
            return json.loads(clean_json_str)
        else:
            raise Exception("Lỗi cấu trúc định dạng JSON từ Gemini") 
            
    except Exception as e:
        error_msg = str(e)
        danger_keywords = ["tự tử", "chết", "tự sát", "không muốn sống", "tuyệt vọng", "kết thúc", "rạch tay"]
        if any(word in user_input.lower() for word in danger_keywords):
            return {
                "level": "Danger", 
                "reply": "Mình cảm nhận được bạn đang chịu đựng một nỗi đau rất lớn. Hãy dừng lại một chút, mình luôn ở đây nghe bạn. Đồng thời, mình đã phát tín hiệu khẩn cấp đến thầy cô và gia đình để hỗ trợ bạn ngay lập tức. Bạn không cô đơn đâu! ❤️"
            }
        
        if "429" in error_msg or "quota" in error_msg.lower():
            return {"level": "Safe", "reply": "Mình đang bận xử lý dữ liệu một chút. Bạn chờ khoảng 30 giây rồi gửi lại ảnh/tin nhắn giúp mình nhé! 💙"}
        
        return {"level": "Safe", "reply": "Mình đã nhận được hình ảnh khuôn mặt của bạn. Nhìn bạn có vẻ đang có nhiều tâm sự đúng không? Hãy nói cho mình biết rõ hơn nhé!"}

# ==========================================
# CÁC ROUTE ĐIỀU HƯỚNG FLASK
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
        db[code] = {
            "ten": name,
            "phu_huynh_id": parent_id if parent_id else None
        }
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
        
        db = load_db()
        student_name = "Học sinh Ẩn danh"
        parent_id = None
        
        if student_code in db:
            student_name = db[student_code]["ten"]
            parent_id = db[student_code]["phu_huynh_id"]
            
        data = get_ai_response(user_msg, base64_image=chat_image)
        if not data or not isinstance(data, dict):
            data = {"level": "Safe", "reply": "Mình vẫn đang ở đây đồng hành cùng bạn."}
        
        # Nếu quét ra biểu cảm nguy hiểm hoặc nhắn tin tiêu cực, kích hoạt gửi Telegram lập tức
        if data.get('level') == 'Danger':
            send_alert(user_msg, data.get('reply'), TEACHER_CHAT_ID, "Giáo viên", student_code, student_name)
            if parent_id:
                send_alert(user_msg, data.get('reply'), parent_id, "Phụ huynh", student_code, student_name)
                
        return jsonify(data)

    except Exception as global_err:
        traceback.print_exc()
        return jsonify({"level": "Safe", "reply": "Hệ thống camera kết nối bị lag. Bạn quét lại hoặc nhắn tin nhé!"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
