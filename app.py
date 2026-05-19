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
TELEGRAM_TOKEN = "8561921353:AAF8mzyV6ZEIe-x3eiwJEgQX90C1pKSngF"
TELEGRAM_CHAT_ID = "5871331291"

# THÔNG TIN XÁC THỰC MESSENGER META
VERIFY_TOKEN = "MINDGUARD_123"
PAGE_ACCESS_TOKEN = "EAATQZCqcM1PsBRQq0QOHvNwYY0MxHgOhrrm1AbRvijw5ZCzGueZAzmSsRGmeAw7Q9HRBsaN90CxTLgiomZAcZBGckvxZAyFkL6lmOVIGqiDHfq522GHyjGFYZAK8JJ6vtxN6ZCI7oWBTZAJFSrtE3ZALSIGBZB1GOKbXl1A8KZASZBRZC8iOqtjpHrxnx4xCwNQ5GZBu0uWqGVo"

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
# HÀM BỔ TRỢ (TELEGRAM & AI)
# ==========================================
def send_alert(msg, reply):
    # Định dạng tin nhắn viết hoa, rõ ràng y như ảnh mẫu của bạn
    text = (
        "🚨 CANH BAO MINDGUARD 🚨\n"
        f"HS: {msg}\n"
        f"AI: {reply}"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
    except:
        pass

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
        error_msg = str(e)
        
        # LƯỚI AN TOÀN DỰ PHÒNG (EMERGENCY FALLBACK)
        danger_keywords = ["tự tử", "chết", "tự sát", "không muốn sống", "tuyệt vọng", "kết thúc"]
        if any(word in user_input.lower() for word in danger_keywords):
            return {
                "level": "Danger",
                "reply": "Mình nhận thấy bạn đang có suy nghĩ rất tiêu cực. Dù hệ thống chat đang gặp chút sự cố quá tải, nhưng mình đã lập tức gửi tín hiệu khẩn cấp..."
            }
        if "429" in error_msg or "quota" in error_msg.lower():
            return {"level": "Safe", "reply": "Mình đang có hơi nhiều bạn cùng tâm sự nên bị quá tải một chút..."}
            
        return {"level": "Error", "reply": "Hệ thống đang bảo trì hoặc gặp sự cố. Bạn quay lại sau ít phút nhé!"}


# ==========================================
# CÁC ROUTE WEB GIAO DIỆN CŨ
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

    ai_data = get_ai_response(user_msg)
    if ai_data.get('level') == 'Danger':
        send_alert(user_msg, ai_data.get('reply'))
        
    return jsonify(ai_data)


# ==========================================
# ROUTE WEBHOOK TIẾP NHẬN MESSENGER META
# ==========================================
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        return "Xác minh thất bại", 403

    elif request.method == 'POST':
        data = request.get_json()
        if data and data.get('object') == 'page':
            for entry in data['entry']:
                for messaging_event in entry.get('messaging', []):
                    if messaging_event.get('message') and messaging_event['message'].get('text'):
                        sender_id = messaging_event['sender']['id']
                        user_message = messaging_event['message']['text']
                        
                        # Gọi bộ não AI xử lý câu trả lời
                        ai_data = get_ai_response(user_message)
                        bot_reply = ai_data.get('reply', 'Hệ thống bận.')
                        
                        # Bắn cảnh báo Telegram nếu học sinh nhắn tin Danger qua Messenger
                        if ai_data.get('level') == 'Danger':
                            send_alert(user_message, bot_reply)
                        
                        # Gửi câu trả lời về cho Facebook Messenger
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
        print("Lỗi gửi tin nhắn API Meta:", e)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
