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

# Kết nối model AI phù hợp
try:
    valid_models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    chosen_model = 'gemini-1.5-flash' if 'gemini-1.5-flash' in valid_models else valid_models[0]
except Exception:
    chosen_model = 'gemini-1.5-flash'

model = genai.GenerativeModel(chosen_model)
print(f"🧠 MINDGUARD ĐÃ KẾT NỐI VỚI MODEL AI: {chosen_model}")

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

# ==========================================
# KHU VỰC SỬA LỖI ĐỊNH DẠNG ẢNH BASE64 SANG BYTES
# ==========================================
def parse_base64_image(base64_str):
    try:
        if base64_str and "," in base64_str:
            header, base64_data = base64_str.split(",", 1)
            mime_type = header.split(";")[0].split(":")[1]
            
            # ĐÃ SỬA TẠI ĐÂY: Giải mã chuỗi văn bản Base64 thành dữ liệu Bytes thô để Gemini đọc được
            img_bytes = base64.b64decode(base64_data)
            
            return {"mime_type": mime_type, "data": img_bytes}
    except Exception as e:
        print(f"Lỗi phân tích Base64 ảnh: {e}")
    return None

# ==========================================
# HÀM XỬ LÝ LÕI AI GEMINI (PHÂN TÍCH KHUÔN MẶT THỰC TẾ)
# ==========================================
def get_ai_response(user_input, base64_image=None):
    system_prompt = (
        "Bạn là MindGuard - Chuyên gia tâm lý học đường chữa lành tổn thương tinh thần.\n"
        "Hãy lắng nghe thấu cảm sâu sắc, hỗ trợ giảm nhẹ áp lực học tập và cuộc sống.\n"
        "Nhiệm vụ của bạn là phân tích nội dung học sinh cung cấp bao gồm văn bản và hình ảnh.\n"
        "ĐẶC BIỆT: Nếu có hình ảnh khuôn mặt gửi kèm từ webcam, hãy đóng vai trò như một máy quét cảm xúc thông minh. "
        "Hãy nhìn thật kỹ biểu cảm (nụ cười, ánh mắt, chân mày, cơ mặt, cử chỉ) để đoán xem bạn ấy đang thực sự vui vẻ, "
        "hay đang cười gượng, u sầu, mệt mỏi, áp lực, lo lắng hoặc bất an, rồi đưa ra lời nhận xét thấu cảm chân thành, cá nhân hóa nhất theo bức ảnh.\n\n"
        "Sau đó, phân loại tình trạng theo 3 mức độ nguy hiểm:\n"
        "- 'Safe': Trò chuyện thông thường, chia sẻ áp lực nhẹ, hoặc khuôn mặt bình thường/vui vẻ.\n"
        "- 'Warning': Có dấu hiệu khủng hoảng tinh thần nhẹ, khuôn mặt u sầu, kiệt quệ, khóc lóc.\n"
        "- 'Danger': Có ý định làm đau bản thân, tự tử, hoặc hình ảnh thể hiện sự thương tổn nguy hiểm.\n\n"
        "BẮT BUỘC CHỈ TRẢ VỀ ĐÚNG ĐỊNH DẠNG KHỐI JSON, KHÔNG THÊM BẤT KỲ KÝ TỰ HOẶC CHỮ NÀO KHÁC NGOÀI KHỐI JSON NÀY:\n"
        '{"level": "Safe/Warning/Danger", "reply": "Nội dung phản hồi nhẹ nhàng, thấu cảm sâu sắc, nhận xét chi tiết dựa trên biểu cảm khuôn mặt trong ảnh bằng tiếng Việt"}'
    )
    
    # Điều chỉnh câu lệnh nếu phát hiện đây là ảnh quét tự động từ camera của hệ thống
    prompt_text = user_input
    if "[Hệ thống]" in user_input:
        prompt_text = "Tôi vừa thực hiện quét khuôn mặt của mình bằng webcam trực tiếp. Hãy nhìn bức ảnh đi kèm, phân tích biểu cảm khuôn mặt hiện tại của tôi xem tôi đang cảm thấy thế nào và trò chuyện trò chuyện cùng tôi nhé."

    contents = [system_prompt, f"Yêu cầu từ học sinh: '{prompt_text}'"]
    
    if base64_image:
        image_part = parse_base64_image(base64_image)
        if image_part:
            contents.append(image_part)

    try:
        response = model.generate_content(contents)
        raw_text = response.text.strip()
        
        # Trích xuất chuỗi cấu trúc JSON đề phòng AI sinh thừa ký tự markdown
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_json_str = raw_text[start_idx:end_idx+1]
            return json.loads(clean_json_str)
        else:
            raise Exception("Lỗi cấu trúc định dạng JSON từ Gemini") 
            
    except Exception as e:
        print(f"❌ Gặp lỗi khi gọi Gemini API: {e}")
        # Cơ chế bắt lỗi dự phòng tự động khi hệ thống quá tải hoặc gặp từ khóa nguy hiểm
        danger_keywords = ["tự tử", "chết", "tự sát", "không muốn sống", "tuyệt vọng", "kết thúc", "rạch tay"]
        if any(word in user_input.lower() for word in danger_keywords):
            return {
                "level": "Danger", 
                "reply": "Mình cảm nhận được bạn đang chịu đựng một nỗi đau rất lớn. Hãy dừng lại một chút, mình luôn ở đây nghe bạn. Đồng thời, mình đã phát tín hiệu khẩn cấp đến thầy cô và gia đình để hỗ trợ bạn ngay lập tức. Bạn không cô đơn đâu! ❤️"
            }
        
        if "429" in str(e) or "quota" in str(e).lower():
            return {"level": "Safe", "reply": "Hệ thống AI đang nhận quá nhiều lượt quét ảnh cùng lúc. Bạn chờ khoảng 10 giây rồi bấm gửi lại ảnh giúp mình nhé! 💙"}
        
        return {"level": "Safe", "reply": "Mình đã nhận được ảnh khuôn mặt của bạn. Nhìn bạn có vẻ đang mang nhiều suy tư đúng không? Hãy nhắn tin chia sẻ rõ hơn với mình nha!"}

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
            data = {"level": "Safe", "reply": "Mình vẫn đang ở đây đồng hành và lắng nghe bạn."}
        
        # Nếu quét ra biểu cảm nguy hiểm hoặc nhắn tin có xu hướng tiêu cực nặng
        if data.get('level') == 'Danger':
            send_alert(user_msg, data.get('reply'), TEACHER_CHAT_ID, "Giáo viên", student_code, student_name)
            if parent_id:
                send_alert(user_msg, data.get('reply'), parent_id, "Phụ huynh", student_code, student_name)
                
        return jsonify(data)

    except Exception as global_err:
        traceback.print_exc()
        return jsonify({"level": "Safe", "reply": "Hệ thống camera đang kết nối lại. Bạn hãy quét lại biểu cảm hoặc nhắn tin cho mình nhé!"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
