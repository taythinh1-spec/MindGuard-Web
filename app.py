"""
MindGuard AI — Trợ lý tâm lý học đường
Backend Flask + Google Gemini 1.5 Flash
"""

# === THƯ VIỆN CHUẨN ===
import base64
import json
import logging
import os
import traceback

# === THƯ VIỆN BÊN NGOÀI ===
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

# ============================================================
# KHỞI TẠO
# ============================================================

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================
# CẤU HÌNH BẢO MẬT — ĐỌC TỪ BIẾN MÔI TRƯỜNG
# ⚠️  TUYỆT ĐỐI KHÔNG hardcode token vào đây!
#     Khai báo trong file .env (local) hoặc Render dashboard:
#       GEMINI_API_KEY=AIza...
#       TELEGRAM_TOKEN=8561...
#       TEACHER_CHAT_ID=5871...
# ============================================================

GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TEACHER_CHAT_ID  = os.environ.get("TEACHER_CHAT_ID", "")

if not GEMINI_API_KEY:
    logger.critical("Chưa tìm thấy GEMINI_API_KEY trong biến môi trường!")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Đã cấu hình Google Gemini AI.")

# ============================================================
# CƠ SỞ DỮ LIỆU JSON CỤC BỘ
# ============================================================

DB_FILE = "students.json"


def load_db() -> dict:
    """Tải dữ liệu học sinh từ file JSON. Trả về dict rỗng nếu lỗi."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Lỗi đọc DB: %s", e)
        return {}


def save_db(data: dict) -> None:
    """Ghi dữ liệu học sinh xuống file JSON."""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error("Lỗi ghi DB: %s", e)


# ============================================================
# KHỞI TẠO MODEL GEMINI (một lần khi server start)
# ============================================================

try:
    _valid = [
        m.name.replace("models/", "")
        for m in genai.list_models()
        if "generateContent" in m.supported_generation_methods
    ]
    CHOSEN_MODEL = "gemini-1.5-flash" if "gemini-1.5-flash" in _valid else (_valid[0] if _valid else "gemini-1.5-flash")
except Exception:
    CHOSEN_MODEL = "gemini-1.5-flash"

gemini_model = genai.GenerativeModel(CHOSEN_MODEL)
logger.info("MindGuard đã kết nối model AI: %s", CHOSEN_MODEL)

# ============================================================
# HẰNG SỐ — PROMPT HỆ THỐNG
# ============================================================

SYSTEM_PROMPT = """Bạn là MindGuard — một hệ thống AI phân tích sinh trắc học cảm xúc chuyên nghiệp kiêm chuyên gia tâm lý học đường.

NHIỆM VỤ CHÍNH:
Khi nhận được ảnh khuôn mặt từ webcam, hãy đóng vai máy quét cảm xúc tiên tiến. Phân tích cực kỳ tỉ mỉ:
- Mắt: ánh nhìn, độ mở mắt, vùng dưới mắt (thâm quầng, mệt mỏi)
- Miệng và nụ cười: tươi tắn / gượng / mím chặt
- Chân mày: cau lại / nhướn / bình thường
- Cơ mặt tổng thể: căng thẳng / thư giãn / kiệt sức

SAU ĐÓ:
1. Lồng ghép các chỉ số cảm xúc dưới dạng phần trăm vào đầu câu trả lời theo mẫu:
   📊 Bảng sinh trắc cảm xúc:  Vui vẻ: XX% | Lo âu: XX% | Mệt mỏi: XX% | Bình tĩnh: XX%
   (Tổng bằng 100%. Chọn 3-4 cảm xúc phù hợp nhất.)
2. Viết một đoạn phân tích thấu cảm, cá nhân hóa dựa trên ảnh, nhẹ nhàng và chữa lành.
3. Đặt một câu hỏi mở để khuyến khích học sinh chia sẻ thêm.

PHÂN LOẠI MỨC ĐỘ:
- "Safe": Bình thường, vui vẻ, áp lực nhẹ thông thường.
- "Warning": Dấu hiệu khủng hoảng nhẹ: kiệt sức, u sầu, Lo âu cao (>50%), khóc lóc.
- "Danger": Có ý định tự làm hại, tự tử, hoặc ảnh thể hiện thương tổn nghiêm trọng.

QUY TẮC BẮT BUỘC:
- Toàn bộ phản hồi bằng tiếng Việt, ấm áp, không phán xét.
- Chỉ trả về JSON thuần, không markdown, không giải thích thêm.
- Định dạng chính xác: {"level": "Safe|Warning|Danger", "reply": "Nội dung phân tích và trò chuyện"}"""

# Từ khóa nguy hiểm để bắt lỗi dự phòng khi Gemini không phản hồi
DANGER_KEYWORDS = [
    "tự tử", "chết", "tự sát", "không muốn sống",
    "tuyệt vọng", "kết thúc tất cả", "rạch tay", "nhảy lầu",
]

# Các dòng trạng thái hiển thị trên progress bar (gửi về frontend)
LOADING_STAGES = [
    "Đang định vị khuôn mặt...",
    "Đang phân tích các cơ mặt...",
    "Đang đo lường biểu cảm mắt và miệng...",
    "AI đang giải mã cảm xúc sâu...",
    "Đang tổng hợp báo cáo tâm lý...",
]

# ============================================================
# HÀM TIỆN ÍCH
# ============================================================

def parse_base64_image(base64_str: str) -> dict | None:
    """
    Giải mã chuỗi Base64 từ frontend thành dict {mime_type, data}
    dạng bytes thô mà Gemini SDK yêu cầu.
    Hỗ trợ header 'data:image/...;base64,' hoặc chuỗi thuần.
    """
    try:
        if not base64_str:
            return None
        if "," in base64_str:
            header, raw = base64_str.split(",", 1)
            # Trích xuất mime_type từ header (vd: data:image/jpeg;base64)
            mime_type = header.split(";")[0].split(":")[1] if ":" in header else "image/jpeg"
        else:
            raw = base64_str
            mime_type = "image/jpeg"

        # Giải mã thành bytes thô — đây là định dạng Gemini SDK yêu cầu
        img_bytes = base64.b64decode(raw)
        return {"mime_type": mime_type, "data": img_bytes}
    except Exception as e:
        logger.error("Lỗi parse Base64 ảnh: %s", e)
        return None


def extract_json(raw_text: str) -> dict:
    """
    Trích xuất JSON từ phản hồi của Gemini.
    Xử lý an toàn khi AI bọc JSON trong markdown ```json ... ```.
    """
    # Loại bỏ markdown code block nếu có
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Bỏ dòng đầu (```json) và dòng cuối (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    # Tìm cặp ngoặc nhọn JSON đầu tiên và cuối cùng
    start = cleaned.find("{")
    end   = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Không tìm thấy cấu trúc JSON trong phản hồi AI.")

    return json.loads(cleaned[start : end + 1])


def get_fallback_response(user_input: str) -> dict:
    """Phản hồi dự phòng khi Gemini API lỗi hoặc quá tải."""
    msg_lower = user_input.lower()
    if any(kw in msg_lower for kw in DANGER_KEYWORDS):
        return {
            "level": "Danger",
            "reply": (
                "Mình cảm nhận được bạn đang chịu đựng một nỗi đau rất lớn. "
                "Hãy dừng lại một chút — mình luôn ở đây lắng nghe bạn. "
                "Mình đã gửi tín hiệu hỗ trợ đến thầy cô để giúp bạn ngay. "
                "Bạn không cô đơn đâu nhé! ❤️"
            ),
        }
    return {
        "level": "Safe",
        "reply": (
            "Mình đã nhận được ảnh của bạn rồi! Hệ thống đang xử lý hơi chậm "
            "do lưu lượng cao. Bạn hãy nhắn thêm vài chữ để mình hiểu bạn "
            "đang cảm thấy thế nào nhé? 💙"
        ),
    }


def get_ai_response(user_input: str, base64_image: str | None = None) -> dict:
    """
    Gọi Gemini AI phân tích văn bản + ảnh khuôn mặt.
    Trả về dict {"level": str, "reply": str}.
    """
    # Chuẩn hóa prompt nếu là quét ảnh tự động từ hệ thống
    if "[Hệ thống]" in user_input:
        prompt_text = (
            "Tôi vừa cho webcam chụp lại khuôn mặt của mình. "
            "Hãy nhìn kỹ bức ảnh đi kèm, phân tích biểu cảm và "
            "cho tôi biết bạn đọc ra cảm xúc gì từ khuôn mặt tôi nhé."
        )
    else:
        prompt_text = user_input

    contents = [SYSTEM_PROMPT, f"Yêu cầu từ học sinh: '{prompt_text}'"]

    if base64_image:
        image_part = parse_base64_image(base64_image)
        if image_part:
            contents.append(image_part)

    try:
        response  = gemini_model.generate_content(contents)
        result    = extract_json(response.text)

        # Kiểm tra cấu trúc tối thiểu
        if "level" not in result or "reply" not in result:
            raise ValueError("JSON thiếu trường bắt buộc.")

        # Đảm bảo level hợp lệ
        if result["level"] not in ("Safe", "Warning", "Danger"):
            result["level"] = "Safe"

        return result

    except Exception as e:
        logger.error("Lỗi Gemini AI: %s", e)
        # Phân biệt lỗi quota để thông báo phù hợp
        if "429" in str(e) or "quota" in str(e).lower():
            return {
                "level": "Safe",
                "reply": (
                    "Hệ thống AI đang nhận quá nhiều yêu cầu cùng lúc. "
                    "Bạn chờ khoảng 10 giây rồi thử lại nhé! 💙"
                ),
            }
        return get_fallback_response(user_input)


def send_telegram_alert(
    message: str,
    ai_reply: str,
    chat_id: str,
    role: str,
    student_code: str,
    student_name: str,
) -> None:
    """
    Gửi cảnh báo khẩn cấp qua Telegram bot.
    Bỏ qua im lặng nếu TELEGRAM_TOKEN chưa được cấu hình.
    """
    if not TELEGRAM_TOKEN or not chat_id:
        logger.warning("Chưa cấu hình TELEGRAM_TOKEN hoặc chat_id — bỏ qua cảnh báo.")
        return

    text = (
        f"🚨 MINDGUARD CẢNH BÁO ({role}) 🚨\n"
        f"👤 Học sinh: {student_name} (Mã: {student_code})\n"
        f"💬 Nội dung: {message}\n"
        f"🤖 Phân tích AI: {ai_reply}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=5)
        logger.info("Đã gửi cảnh báo Telegram đến %s (%s).", student_name, role)
    except requests.RequestException as e:
        logger.error("Lỗi gửi Telegram (%s): %s", role, e)


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    """Trang chủ giao diện chính."""
    return render_template("index.html")


@app.route("/register", methods=["POST"])
def register():
    """Đăng ký / cập nhật hồ sơ học sinh vào DB cục bộ."""
    try:
        data        = request.get_json(silent=True) or {}
        code        = data.get("student_code", "").upper().strip()
        name        = data.get("student_name", "").strip()
        parent_id   = data.get("parent_id", "").strip()

        if not code or not name:
            return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ mã học sinh và họ tên!"}), 400

        db = load_db()
        db[code] = {"ten": name, "phu_huynh_id": parent_id or None}
        save_db(db)
        logger.info("Đã đăng ký học sinh: %s (%s)", name, code)
        return jsonify({"status": "success", "message": f"Đã lưu hồ sơ cho {name}!"})

    except Exception as e:
        logger.exception("Lỗi tại /register")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    """
    Nhận tin nhắn + ảnh webcam → gọi Gemini AI phân tích
    → gửi cảnh báo Telegram nếu mức Danger → trả JSON về frontend.
    """
    try:
        data_req     = request.get_json(silent=True) or {}
        user_msg     = data_req.get("message", "")
        student_code = data_req.get("student_code", "KH").upper().strip()
        chat_image   = data_req.get("image", None)

        # Lấy thông tin học sinh từ DB
        db           = load_db()
        student_info = db.get(student_code, {})
        student_name = student_info.get("ten", "Học sinh Ẩn danh")
        parent_id    = student_info.get("phu_huynh_id", None)

        # Gọi AI
        result = get_ai_response(user_msg, base64_image=chat_image)
        if not isinstance(result, dict):
            result = {"level": "Safe", "reply": "Mình vẫn đang ở đây đồng hành cùng bạn."}

        # Gửi cảnh báo nếu phát hiện nguy hiểm
        if result.get("level") == "Danger":
            send_telegram_alert(
                user_msg, result.get("reply", ""),
                TEACHER_CHAT_ID, "Giáo viên", student_code, student_name,
            )
            if parent_id:
                send_telegram_alert(
                    user_msg, result.get("reply", ""),
                    parent_id, "Phụ huynh", student_code, student_name,
                )

        return jsonify(result)

    except Exception:
        logger.exception("Lỗi không xác định tại /chat")
        return jsonify({
            "level": "Safe",
            "reply": "Hệ thống đang tải lại. Bạn hãy nhắn tin hoặc quét lại sau vài giây nhé!",
        })


# ============================================================
# ĐIỂM KHỞI ĐỘNG
# ============================================================

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
