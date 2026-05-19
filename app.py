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
TELEGRAM_CHAT_ID = "5871531291" 

genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# TỰ ĐỘNG KẾT NỐI MODEL AI PHÙ HỢP
# ==========================================
valid_models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
if 'gemini-1.5-flash' in valid_models:
    chosen_model = 'gemini-1.5-flash'
elif 'gemini-pro' in valid_models:
    chosen_model = 'gemini-pro'
else:
    chosen_model = valid_models[0]

model = genai.GenerativeModel(chosen_model)
print(f"🧠 MINDGUARD ĐÃ KẾT NỐI VỚI MODEL: {chosen_model}")

# ==========================================
# HÀM GỬI CẢNH BÁO TELEGRAM
# ==========================================
def send_alert(msg, reply):
    text = f"🚨 CẢNH BÁO MỨC ĐỘ NGUY HIỂM! \nHọc sinh: {msg}\nBot: {reply}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
        print("\n=== KẾT QUẢ GỬI TELEGRAM ===", flush=True)
        print(response.json(), flush=True)
        print("============================\n", flush=True)
    except Exception as e:
        print(f"\n=== LỖI KẾT NỐI TELEGRAM: {e} ===\n", flush=True)

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
        
        print("\n=== AI TRẢ VỀ GỐC ===", flush=True)
        print(raw_text, flush=True) 
        print("=====================\n", flush=True)
        
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_json_str = raw_text[start_idx:end_idx+1]
            return json.loads(clean_json_str)
        else:
            raise Exception("Lỗi định dạng JSON từ AI") 
            
    except Exception as e:
        error_msg = str(e)
        print(f"\n=== LỖI HỆ THỐNG AI: {error_msg} ===\n", flush=True)
        
        # --- 🚨 LƯỚI AN TOÀN DỰ PHÒNG 🚨 ---
        danger_keywords = ["tự tử", "chết", "tự sát", "không muốn sống", "tuyệt vọng", "kết thúc"]
        if any(word in user_input.lower() for word in danger_keywords):
            return {
                "level": "Danger", 
                "reply": "Mình nhận thấy bạn đang có suy nghĩ rất tiêu cực. Dù hệ thống chat đang gặp chút sự cố, nhưng mình đã lập tức gửi tín hiệu khẩn cấp đến thầy cô. Xin bạn hãy bình tĩnh, sẽ có người liên hệ hỗ trợ bạn ngay!"
            }
        
        if "429" in error_msg or "quota" in error_msg.lower():
            return {"level": "Safe", "reply": "Mình đang có hơi nhiều bạn cùng tâm sự nên bị quá tải một chút. Bạn cho mình nghỉ ngơi khoảng 1 phút rồi nhắn lại nhé! 💙"}
        
        return {"level": "Error", "reply": "Hệ thống đang bảo trì hoặc gặp sự cố. Bạn quay lại sau ít phút nhé!"}

# ==========================================
# CÁC ROUTE GIAO DIỆN WEB
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data_req = request.json
        if not data_req:
            return jsonify({"level": "Error", "reply": "Không nhận được dữ liệu yêu cầu."}), 400
            
        user_msg = data_req.get('message', '')
        image_base64 = data_req.get('image', '')
        user_name = data_req.get('user_name', 'Học sinh')
        
        # 1. Xử lý ảnh gửi lên Telegram (nếu có)
        if image_base64:
            try:
                img_data = image_base64.split(',')[1]
                img_bytes = base64.b64decode(img_data)
                
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                caption = f"📸 Ảnh gửi từ: {user_name}"
                if user_msg:
                    caption += f"\n💬 Tin nhắn kèm theo: {user_msg}"
                    
                files = {'photo': ('image.png', img_bytes)}
                payload = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
                requests.post(url, data=payload, files=files, timeout=5)
            except Exception as e:
                print("Lỗi gửi ảnh lên Telegram:", e, flush=True)
                
        # 2. Xử lý logic nếu chỉ gửi ảnh (không có chữ)
        if not user_msg.strip() and image_base64:
            return jsonify({"level": "Safe", "reply": "Mình đã nhận được bức ảnh của bạn rồi nhé! Bức ảnh này có ý nghĩa gì với bạn thế?"})
            
        # 3. Lấy phản hồi từ AI / Lưới an toàn
        data = get_ai_response(user_msg)
        
        # Đảm bảo dữ liệu luôn là một Dictionary hợp lệ
        if not data or not isinstance(data, dict):
            data = {"level": "Error", "reply": "Hệ thống đang bận, bạn đợi mình một xíu nhé!"}
        
        # 4. Kích hoạt cảnh báo Telegram nếu là Danger
        if data.get('level') == 'Danger':
            send_alert(user_msg, data.get('reply'))
            
        # 5. Trả về kết quả cho web
        return jsonify(data)

    except Exception as global_err:
        print(f"\n❌ LỖI HỆ THỐNG TẠI ROUTE CHAT: {global_err} \n", flush=True)
        traceback.print_exc()
        return jsonify({"level": "Error", "reply": "Hệ thống đang gặp sự cố nhỏ. Bạn thử lại sau vài giây nhé!"})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
