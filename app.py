import base64
import json
import logging
import os
import traceback

# === THƯ VIỆN BÊN NGOÀI ===
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

# SDK MỚI — thay thế google.generativeai đã bị khai tử
from google import genai
from google.genai import types

# ============================================================
# KHỞI TẠO
# ============================================================

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================
# CẤU HÌNH BẢO MẬT — ĐỌC TỪ BIẾN MÔI TRƯỜNG
# Khai báo trên Render dashboard hoặc file .env (local):
#   GEMINI_API_KEY=AIza...
#   TELEGRAM_TOKEN=85619...
#   TEACHER_CHAT_ID=5871...
# ============================================================

GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN", "")
TEACHER_CHAT_ID = os.environ.get("TEACHER_CHAT_ID", "")

if not GEMINI_API_KEY:
    logger.critical("Chưa tìm thấy GEMINI_API_KEY trong biến môi trường!")

# Khởi tạo Gemini client theo SDK mới (một lần duy nhất)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
CHOSEN_MODEL   = "gemini-2.0-flash"   # Model mới nhất, ổn định, miễn phí
logger.info("MindGuard đã kết nối model AI: %s", CHOSEN_MODEL)

# ============================================================
# CƠ SỞ DỮ LIỆU JSON CỤC BỘ
# ============================================================

DB_FILE = "students.json"


def load_db() -> dict:
    """Tải dữ liệu học sinh từ file JSON."""
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
# HẰNG SỐ — PROMPT HỆ THỐNG
# ============================================================

SYSTEM_PROMPT = """Bạn là MindGuard — hệ thống AI phân tích sinh trắc học cảm xúc kiêm chuyên gia tâm lý học đường.

NHIỆM VỤ KHI CÓ ẢNH KHUÔN MẶT:
Phân tích cực kỳ tỉ mỉ: mắt (ánh nhìn, độ mở, thâm quầng), miệng (nụ cười tươi/gượng/mím), chân mày (cau/nhướn/thư giãn), cơ mặt tổng thể.

SAU ĐÓ THỰC HIỆN:
1. Xuất bảng sinh trắc cảm xúc ở đầu reply theo mẫu:
   📊 Bảng sinh trắc: Vui vẻ: XX% | Lo âu: XX% | Mệt mỏi: XX% | Bình tĩnh: XX%
   (Tổng = 100%, chọn 3-4 cảm xúc phù hợp nhất với khuôn mặt trong ảnh)
2. Viết 2-3 câu phân tích thấu cảm, cá nhân hóa theo biểu cảm quan sát được.
3. Đặt 1 câu hỏi mở để khuyến khích học sinh chia sẻ thêm.

PHÂN LOẠI MỨC ĐỘ (bắt buộc chọn 1):
- "Safe": Bình thường, vui, áp lực nhẹ thông thường.
- "Warning": Kiệt sức, u sầu, lo âu cao (>50%), dấu hiệu khủng hoảng nhẹ.
- "Danger": Có ý định tự làm hại, tự tử, hoặc ảnh thể hiện thương tổn nguy hiểm.

QUY TẮC BẮT BUỘC:
- Toàn bộ tiếng Việt, ấm áp, không phán xét.
- Chỉ trả về JSON thuần. KHÔNG markdown, KHÔNG giải thích thêm.
- Định dạng chính xác: {"level": "Safe|Warning|Danger", "reply": "Nội dung"}"""

DANGER_KEYWORDS = [
    "tự tử", "chết", "tự sát", "không muốn sống",
    "tuyệt vọng", "kết thúc tất cả", "rạch tay", "nhảy lầu",
]

# ============================================================
# HÀM TIỆN ÍCH
# ============================================================

def parse_base64_image(base64_str: str) -> types.Part | None:
    """
    Chuyển chuỗi Base64 từ frontend thành types.Part của SDK google-genai.
    Hỗ trợ header 'data:image/...;base64,' hoặc chuỗi thuần.
    """
    try:
        if not base64_str:
            return None
        if "," in base64_str:
            header, raw = base64_str.split(",", 1)
            mime_type = header.split(";")[0].split(":")[1] if ":" in header else "image/jpeg"
        else:
            raw       = base64_str
            mime_type = "image/jpeg"

        img_bytes = base64.b64decode(raw)
        # SDK mới dùng types.Part.from_bytes()
        return types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
    except Exception as e:
        logger.error("Lỗi parse Base64 ảnh: %s", e)
        return None


def extract_json(raw_text: str) -> dict:
    """
    Trích xuất JSON từ phản hồi Gemini.
    Xử lý an toàn khi AI bọc kết quả trong ```json ... ```.
    """
    cleaned = raw_text.strip()
    # Loại bỏ markdown code block nếu có
    if "```" in cleaned:
        lines   = cleaned.split("\n")
        lines   = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    start = cleaned.find("{")
    end   = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Không tìm thấy JSON trong phản hồi AI.")

    return json.loads(cleaned[start : end + 1])


def get_fallback_response(user_input: str) -> dict:
    """Phản hồi dự phòng khi Gemini API lỗi hoặc quá tải."""
    if any(kw in user_input.lower() for kw in DANGER_KEYWORDS):
        return {
            "level": "Danger",
            "reply": (
                "Mình cảm nhận được bạn đang chịu đựng một nỗi đau rất lớn. "
                "Hãy dừng lại — mình luôn ở đây lắng nghe. "
                "Mình đã gửi tín hiệu hỗ trợ đến thầy cô để giúp bạn ngay. "
                "Bạn không cô đơn đâu nhé! ❤️"
            ),
        }
    return {
        "level": "Safe",
        "reply": (
            "Hệ thống AI đang bận xử lý. Bạn hãy nhắn thêm vài chữ "
            "để mình hiểu bạn đang cảm thấy thế nào nhé? 💙"
        ),
    }


def get_ai_response(user_input: str, base64_image: str | None = None) -> dict:
    """
    Gọi Gemini AI phân tích văn bản + ảnh khuôn mặt.
    Sử dụng google-genai SDK mới (client.models.generate_content).
    """
    if "[Hệ thống]" in user_input:
        prompt_text = (
            "Tôi vừa cho webcam chụp khuôn mặt của mình. "
            "Hãy nhìn kỹ bức ảnh, phân tích biểu cảm và cho tôi biết "
            "bạn đọc ra cảm xúc gì từ khuôn mặt tôi nhé."
        )
    else:
        prompt_text = user_input

    # Xây dựng danh sách parts cho SDK mới
    parts = [
        types.Part.from_text(text=SYSTEM_PROMPT),
        types.Part.from_text(text=f"Yêu cầu từ học sinh: '{prompt_text}'"),
    ]

    if base64_image:
        img_part = parse_base64_image(base64_image)
        if img_part:
            parts.append(img_part)

    try:
        response = gemini_client.models.generate_content(
            model=CHOSEN_MODEL,
            contents=parts,
        )
        result = extract_json(response.text)

        if "level" not in result or "reply" not in result:
            raise ValueError("JSON thiếu trường bắt buộc.")
        if result["level"] not in ("Safe", "Warning", "Danger"):
            result["level"] = "Safe"

        return result

    except Exception as e:
        logger.error("Lỗi Gemini AI: %s", e)
        if "429" in str(e) or "quota" in str(e).lower():
            return {
                "level": "Safe",
                "reply": "Hệ thống AI đang nhận quá nhiều yêu cầu. Bạn chờ 10 giây rồi thử lại nhé! 💙",
            }
        return get_fallback_response(user_input)


def send_telegram_alert(
    message: str, ai_reply: str, chat_id: str,
    role: str, student_code: str, student_name: str,
) -> None:
    """Gửi cảnh báo khẩn cấp qua Telegram. Bỏ qua nếu chưa cấu hình token."""
    if not TELEGRAM_TOKEN or not chat_id:
        logger.warning("Chưa cấu hình TELEGRAM_TOKEN hoặc chat_id — bỏ qua cảnh báo.")
        return
    text = (
        f"🚨 MINDGUARD CẢNH BÁO ({role}) 🚨\n"
        f"👤 Học sinh: {student_name} (Mã: {student_code})\n"
        f"💬 Nội dung: {message}\n"
        f"🤖 Phân tích AI: {ai_reply}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5,
        )
        logger.info("Đã gửi cảnh báo Telegram đến %s (%s).", student_name, role)
    except requests.RequestException as e:
        logger.error("Lỗi gửi Telegram (%s): %s", role, e)


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["POST"])
def register():
    """Đăng ký / cập nhật hồ sơ học sinh."""
    try:
        data      = request.get_json(silent=True) or {}
        code      = data.get("student_code", "").upper().strip()
        name      = data.get("student_name", "").strip()
        parent_id = data.get("parent_id", "").strip()

        if not code or not name:
            return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ mã học sinh và họ tên!"}), 400

        db       = load_db()
        db[code] = {"ten": name, "phu_huynh_id": parent_id or None}
        save_db(db)
        logger.info("Đã đăng ký học sinh: %s (%s)", name, code)
        return jsonify({"status": "success", "message": f"Đã lưu hồ sơ cho {name}!"})

    except Exception as e:
        logger.exception("Lỗi tại /register")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    """Nhận tin nhắn + ảnh → gọi AI → gửi Telegram nếu Danger → trả JSON."""
    try:
        data_req     = request.get_json(silent=True) or {}
        user_msg     = data_req.get("message", "")
        student_code = data_req.get("student_code", "KH").upper().strip()
        chat_image   = data_req.get("image", None)

        db           = load_db()
        student_info = db.get(student_code, {})
        student_name = student_info.get("ten", "Học sinh Ẩn danh")
        parent_id    = student_info.get("phu_huynh_id", None)

        result = get_ai_response(user_msg, base64_image=chat_image)
        if not isinstance(result, dict):
            result = {"level": "Safe", "reply": "Mình vẫn đang ở đây đồng hành cùng bạn."}

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
            "reply": "Hệ thống đang tải lại. Bạn hãy thử lại sau vài giây nhé!",
        })


# ============================================================
# ĐIỂM KHỞI ĐỘNG
# ============================================================

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
