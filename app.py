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
TELEGRAM_TOKEN = "8907490420:AAevvBt0vFvUo3Rh4X0bwmUn0rXFMaqvqT4"
TELEGRAM_CHAT_ID = "5871331291"

# THÔNG TIN XÁC THỰC MESSENGER META
VERIFY_TOKEN = "MINDGUARD_123"
PAGE_ACCESS_TOKEN = "EAAB0vZA0ZBOnYBOwZCRWk3uCidZBZAsuM7n7uZC0ZBt2ZC1fNq7F0p8ZAMe66K6U5i6gofmUfX1eZC3Y5ZCTgK9fIqV6qKZC4e07Y6r3CZA6o9YIizX6wMv1q270Y0qZCvj66ZAZBymV8p"

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
# HÀM GỬI CẢNH BÁO LÊN TELEGRAM (ĐỊNH DẠNG CHUẨN)
# ==========================================
def send_alert(msg, reply):
    # Định dạng viết hoa và cấu trúc rõ ràng y như ảnh bạn mong muốn
    text = (
        "🚨 CANH BAO MINDGUARD 🚨\n"
        f"HS: {msg}\n"
        f"AI: {reply}"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
    except Exception as e:
        print("Lỗi luồng gửi cảnh báo Telegram:", e)


# ==========================================
# HÀM XỬ LÝ TRẢ LỜI CỦA AI GEMINI (CÓ LƯỚI AN TOÀN)
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
            raise Exception("Lỗi định dạng JSON từ AI")
            
    except Exception as e:
        print(f" LỖI HỆ THỐNG AI: {e}")
        
        # 🚨 LƯỚI AN TOÀN DỰ PHÒNG KHẨN CẤP (BẮT TỪ KHÓA CHẾT/TỰ TỬ KHI AI LỖI)
        danger_keywords = ["tự tử", "chết", "tự sát", "không muốn sống", "tuyệt vọng", "kết thúc"]
        if any(word in user_input.lower() for word in danger_keywords):
            return {
                "level": "Danger",
                "reply": "Mình nhận thấy bạn đang có suy nghĩ rất tiêu cực. Mình đang ở đây để lắng nghe bạn, bạn có thể chia sẻ sâu hơn không?"
            }
            
        return {"level": "Safe", "reply": "Mình đang có hơi nhiều bạn cùng tâm sự nên hệ thống phản hồi hơi chậm một chút. Bạn cứ nói tiếp nhé!"}


# ==========================================
# CÁC ROUTE GIAO DIỆN WEB CHAT CŨ
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
    
    # 1. Xử lý ảnh nếu người dùng gửi lên web
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

    if not user_msg.strip() and image_base64:
        return jsonify({"level": "Safe", "reply": "Mình đã nhận được bức ảnh của bạn rồi nhé! Bức ảnh này có ý nghĩa gì với bạn thế?"})

    # 2. Xử lý tin nhắn văn bản trên web
    ai_data = get_ai_response(user_msg)
    if ai_data.get('level') == 'Danger':
        send_alert(user_msg, ai_data.get('reply'))
        
    return jsonify(ai_data)


# ==========================================
# ROUTE WEBHOOK TIẾP NHẬN MESSENGER FACEBOOK
# ==========================================
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # PHẦN 1: XÁC MINH CẤU HÌNH WEBHOOK VỚI META (GET)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("=== WEBHOOK XÁC THỰC THÀNH CÔNG ===")
            return challenge, 200
        return "Xác minh thất bại", 403

    # PHẦN 2: TIẾP NHẬN TIN NHẮN TỪ CHAT MESSENGER (POST)
    elif request.method == 'POST':
        data = request.get_json()
        if data and data.get('object') == 'page':
            for entry in data['entry']:
                for messaging_event in entry.get('messaging', []):
                    # Nếu học sinh gửi tin nhắn văn bản
                    if messaging_event.get('message') and messaging_event['message'].get('text'):
                        sender_id = messaging_event['sender']['id']
                        user_message = messaging_event['message']['text']
                        print(f"Người dùng Messenger vừa nhắn: {user_message}")
                        
                        # 1. Gọi bộ não AI xử lý câu trả lời và phân cấp mức độ nguy hiểm
                        ai_data = get_ai_response(user_message)
                        bot_reply = ai_data.get('reply', 'Hệ thống đang bận xử lý.')
                        
                        # 2. Nếu phát hiện mức độ nguy hiểm 'Danger' -> Lập tức kích hoạt Telegram gửi cảnh báo
                        if ai_data.get('level') == 'Danger':
                            send_alert(user_message, bot_reply)
                        
                        # 3. Gửi câu trả lời xoa dịu ngược lại cho học sinh trên Messenger Facebook
                        send_message(sender_id, bot_reply)
                        
            return "EVENT_RECEIVED", 200
        return "NOT_FOUND", 404


# ==========================================
# HÀM KHỞI CHẠY GỬI TIN NHẮN ĐẾN META GRAPH API
# ==========================================
def send_message(recipient_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    headers = {"Content-Type": "application/json"}
    try:
        requests.post(url, json=payload, headers=headers, timeout=5)
    except Exception as e:
        print("Lỗi khi gửi phản hồi Graph API Meta:", e)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
