# custom_gmail/email_analyzer_service.py

import requests
import logging
from markupsafe import Markup

_logger = logging.getLogger(__name__)

def analyze_email_via_gpt(email_text, subject, sender_name, email_from, html_body, message_id=None):
    if not email_text or not email_from or email_from.lower() == "unknown@example.com":
        return {"error": "Email không hợp lệ"}

    try:
        # 🔐 Bước 1: Login để lấy token
        login_payload = {
            "email": "lebadung@wsoftpro.com",
            "password": "zLrA3pN7"
        }
        login_resp = requests.post("http://host.docker.internal:9999/login", json=login_payload, timeout=10)
        if login_resp.status_code != 200:
            _logger.error("❌ Login Flask thất bại: %s", login_resp.text)
            return {"error": "Login thất bại"}

        token = login_resp.json().get("token")
        if not token:
            return {"error": "Không lấy được token"}

        # 🤖 Bước 2: Gửi email tới GPT để phân tích
        payload = {
            "text": email_text,
            "email": email_from,
            "image_base64": None
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }

        gpt_resp = requests.post("http://host.docker.internal:9999/api/status", json=payload, headers=headers, timeout=20)

        if gpt_resp.status_code != 200:
            _logger.error("❌ GPT lỗi: %s", gpt_resp.text)
            return {"error": f"GPT lỗi: {gpt_resp.status_code}"}

        ai_result = gpt_resp.json().get("result", "Không có nội dung")

        return {
            "success": True,
            "ai_result": ai_result,
            "comment_html": Markup(f"""
                <div>
                    <b>✉️ Nội dung Email:</b><br/>{html_body}
                    <hr/>
                    <b>🧠 GPT Phân Tích:</b><br/>{ai_result}
                </div>
            """)
        }

    except Exception as e:
        _logger.exception("❌ Exception trong analyze_email_via_gpt:")
        return {"error": str(e)}
