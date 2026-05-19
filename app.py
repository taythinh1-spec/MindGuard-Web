import os
import json
import base64
import requests
import traceback
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from flask import request
import requests

app = Flask(__name__)
# CẤU HÌNH API KEYS VÀ THÔNG TIN BẢO MẬT
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
TELEGRAM_TOKEN = "8907490420:AAEvvBt0vFvUo3Rh4X0bwmUn0rxFMaqvqT4"
TELEGRAM_CHAT_ID = "5871331291"

genai.configure(api_key=GEMINI_API_KEY)

# TỰ ĐỘNG KẾT NỐI MODEL AI PHÙ HỢP
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
# HÀM GỬI CẢNH BÁO TELEGRAM (KHI GẶP DANGER)
def send_alert(msg, reply):
    text = f"🚨 CẢNH BÁO MỨC ĐỘ NGUY HIỂM! \nHọc sinh: {msg}\nBot: {reply}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
    except:
        pass

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
        
        # In kết quả gốc ra màn hình Log
        print("\n=== AI TRẢ VỀ GỐC ===", flush=True)
        print(raw_text, flush=True) 
        print("=====================\n", flush=True)
        
        # Màng lọc JSON
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_json_str = raw_text[start_idx:end_idx+1]
            return json.loads(clean_json_str)
        else:
            # Ép nhảy xuống except nếu AI trả về linh tinh không phải JSON
            raise Exception("Lỗi định dạng JSON từ AI") 
            
    except Exception as e:
        error_msg = str(e)
        print(f"\n=== LỖI HỆ THỐNG: {error_msg} ===\n", flush=True)
        
        # --- 🚨 LƯỚI AN TOÀN DỰ PHÒNG (EMERGENCY FALLBACK) 🚨 ---
        # Quét từ khóa nguy hiểm để cứu vãn tình hình ngay cả khi máy chủ AI Google bị sập/quá tải
        danger_keywords = ["tự tử", "chết", "tự sát", "không muốn sống", "tuyệt vọng", "kết thúc"]
        if any(word in user_input.lower() for word in danger_keywords):
            return {
                "level": "Danger", 
                "reply": "Mình nhận thấy bạn đang có suy nghĩ rất tiêu cực. Dù hệ thống chat đang gặp chút sự cố quá tải, nhưng mình đã lập tức gửi tín hiệu khẩn cấp đến thầy cô/chuyên gia tâm lý. Xin bạn hãy bình tĩnh, sẽ có người liên hệ hỗ trợ bạn ngay!"
            }
        
        # Bắt lỗi 429 thân thiện (Hết quota / Quá tải) khi không có từ khóa nguy hiểm
        if "429" in error_msg or "quota" in error_msg.lower():
            return {"level": "Safe", "reply": "Mình đang có hơi nhiều bạn cùng tâm sự nên bị quá tải một chút. Bạn cho mình nghỉ ngơi khoảng 1 phút rồi nhắn lại nhé! 💙"}
        
        # Bắt các lỗi hệ thống/mạng khác
        return {"level": "Error", "reply": f"Hệ thống đang bảo trì hoặc gặp sự cố. Bạn quay lại sau ít phút nhé!"}

# ==========================================
# CÁC ROUTE GIAO DIỆN WEB
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data_req = request.json
    user_msg = data_req.get('message', '')
    image_base64 = data_req.get('image', '')
    user_name = data_req.get('user_name', 'Học sinh')
    
    # 1. Xử lý ảnh nếu người dùng gửi lên
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
            print("Lỗi gửi ảnh lên Telegram:", e)
            
    # 2. Xử lý logic nếu chỉ có ảnh mà không có text
    if not user_msg.strip() and image_base64:
        return jsonify({"level": "Safe", "reply": "Mình đã nhận được bức ảnh của bạn rồi nhé! Bức ảnh này có ý nghĩa gì với bạn thế?"})
        
    # 3. Lấy phản hồi từ AI
    data = get_ai_response(user_msg)
    
    # 4. Kích hoạt cảnh báo Telegram nếu AI hoặc Lưới an toàn đánh giá mức độ là Danger
    if data.get('level') == 'Danger':
        send_alert(user_msg, data.get('reply'))
        
    return jsonify(data)
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # --- PHẦN 1: XÁC MINH META (GET) ---
    if request.method == 'GET':
        VERIFY_TOKEN = "MINDGUARD_123"
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        return "Webhook đang hoạt động", 200
        
    # --- PHẦN 2: NHẬN TIN NHẮN TỪ NGƯỜI DÙNG (POST) ---
    elif request.method == 'POST':
        data = request.get_json()
        if data and data.get('object') == 'page':
            for entry in data['entry']:
                for messaging_event in entry.get('messaging', []):
                    # Nếu có tin nhắn văn bản gửi tới
                    if messaging_event.get('message') and messaging_event['message'].get('text'):
                        sender_id = messaging_event['sender']['id']
                        user_message = messaging_event['message']['text']
                        
                        bot_reply = f"MindGuard đã nhận được tin nhắn của bạn: {user_message}"
                        
                        # Lệnh gửi tin nhắn đi
                        send_message(sender_id, bot_reply)
                        
            # Chú ý: return ngang hàng với chữ for đầu tiên
            return "EVENT_RECEIVED", 200
            
        return "NOT_FOUND", 404
                        
def send_message(recipient_id, text):
    PAGE_ACCESS_TOKEN = "EAAbvCpv0bvUBReC2MczQ1Cc8qEZA3Fmotxe96M0zOqIClEMBQV4reZAU99F8YQ5zgPYi9Gm4vb2fht9qIj1ZASt8P1Q3fl8aKJGTtIqsxbPHVbQXNgF1SF7sXmZAlM7ZAudBxwGeT3wrrZBvDKsDLIW1wMf6TZCGL3Bn5YNfLViPEaCPR6Lmq7Te6YV9KZB9Dnl1M07r"
    
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    headers = {"Content-Type": "application/json"}
    requests.post(url, json=payload, headers=headers)
   
if __name__ == '__main__':
    app.run(debug=True, port=8080)
