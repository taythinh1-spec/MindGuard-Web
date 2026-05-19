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

genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# CƠ SỞ DỮ LIỆU TỰ ĐỘNG BẰNG FILE JSON
# ==========================================
DB_FILE = 'students.json'

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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
except:
    chosen_model = 'gemini-1.5-flash'

model = genai.GenerativeModel(chosen_model)
print(f"🧠 MINDGUARD ĐÃ KẾT NỐI VỚI MODEL: {chosen_model}")

# ==========================================
# HÀM GỬI CẢNH BÁO TELEGRAM (ĐỊNH TUYẾN KÉP)
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
# HÀM XỬ LÝ LÕI AI GEMINI (CÓ LƯỚI AN TOÀN)
# ==========================================
def get_ai_response(user_input):
    prompt = f"""Bạn là chuyên gia tâm lý MindGuard AI. Hãy phản hồi: '{user_input}'.
    CHỈ TRẢ VỀ ĐÚNG 1 ĐOẠN JSON, KHÔNG THÊM BẤT KỲ CHỮ HAY KÝ TỰ NÀO KHÁC XUNG QUANH:
    {{"level": "Safe/Warning/Danger", "reply": "nội dung"}}"""
    
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_json_str = raw_text[start_idx:end_idx+1]
            return json.loads(clean_json_str)
        else:
            raise Exception("Lỗi định dạng JSON") 
            
    except Exception as e:
        error_msg = str(e)
        danger_keywords = ["tự tử", "chết", "tự sát", "không muốn sống", "tuyệt vọng", "kết thúc"]
        if any(word in user_input.lower() for word in danger_keywords):
            return {
                "level": "Danger", 
                "reply": "Mình nhận thấy bạn đang có suy nghĩ rất tiêu cực. Mình đã lập tức gửi tín hiệu khẩn cấp đến thầy cô và gia đình. Xin bạn hãy bình tĩnh, sẽ có người hỗ trợ bạn ngay!"
            }
        
        if "429" in error_msg or "quota" in error_msg.lower():
            return {"level": "Safe", "reply": "Mình đang có hơi nhiều bạn cùng tâm sự nên bị quá tải một chút. Bạn cho mình nghỉ ngơi khoảng 1 phút rồi nhắn lại nhé! 💙"}
        
        return {"level": "Error", "reply": "Hệ thống đang bận, bạn đợi mình một xíu nhé!"}

# ==========================================
# CÁC ROUTE ĐIỀU HƯỚNG
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

        if not code or not name or not parent_id:
            return jsonify({"status": "error", "message": "Vui lòng điền đầy đủ tất cả các ô!"}), 400

        db = load_db()
        db[code] = {
            "ten": name,
            "phu_huynh_id": parent_id
        }
        save_db(db)
        return jsonify({"status": "success", "message": "Khai báo thông tin thành công!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data_req = request.json or {}
        user_msg = data_req.get('message', '')
        student_code = data_req.get('student_code', 'Khách').upper().strip()
        
        # Đọc dữ liệu từ file JSON tự động
        db = load_db()
        student_name = "Học sinh Ẩn danh"
        parent_id = None
        
        if student_code in db:
            student_name = db[student_code]["ten"]
            parent_id = db[student_code]["phu_huynh_id"]
            
        # Gọi AI lấy câu trả lời
        data = get_ai_response(user_msg)
        if not data or not isinstance(data, dict):
            data = {"level": "Error", "reply": "Hệ thống đang bận, bạn đợi mình một xíu nhé!"}
        
        # Nếu phát hiện mức độ Danger -> Tiến hành kích hoạt báo động kép
        if data.get('level') == 'Danger':
            # 1. Luôn báo về cho Giáo viên
            send_alert(user_msg, data.get('reply'), TEACHER_CHAT_ID, "Giáo viên", student_code, student_name)
            # 2. Nếu tìm thấy ID phụ huynh của học sinh này -> Báo về cho Phụ huynh
            if parent_id:
                send_alert(user_msg, data.get('reply'), parent_id, "Phụ huynh", student_code, student_name)
                
        return jsonify(data)

    except Exception as global_err:
        traceback.print_exc()
        return jsonify({"level": "Error", "reply": "Hệ thống đang gặp sự cố nhỏ. Thử lại sau nhé!"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
