import requests
import json
import logging
import urllib
from odoo.http import request, Controller
from datetime import datetime, timedelta
from odoo import http
from werkzeug.utils import redirect

_logger = logging.getLogger(__name__)


class GmailAuthController(Controller):
    
    def _get_google_avatar_from_people(self, access_token: str) -> str:
        """
        Lấy avatar của chính user qua People API:
        - Ưu tiên ảnh không phải default (user tự đặt).
        - Nếu URL là ảnh Google (lh3), tăng kích thước lên sz=256.
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            res = requests.get(
                "https://people.googleapis.com/v1/people/me",
                params={"personFields": "photos"},
                headers=headers,
                timeout=10,
            )
            if res.status_code != 200:
                _logger.warning("People API returned %s: %s", res.status_code, res.text)
                return ""

            data = res.json() or {}
            photos = data.get("photos", []) or []
            if not photos:
                return ""

            # Ưu tiên ảnh không default (default=False tốt hơn default=True)
            photos_sorted = sorted(photos, key=lambda p: p.get("default", True))
            url = photos_sorted[0].get("url") or ""
            if not url:
                return ""

            # Nâng size nếu là ảnh Google
            if "lh3.googleusercontent.com" in url:
                if "?" in url:
                    # thay hoặc thêm sz=256
                    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
                    parts = list(urlsplit(url))
                    qs = dict(parse_qsl(parts[3], keep_blank_values=True))
                    qs["sz"] = "256"
                    parts[3] = urlencode(qs)
                    url = urlunsplit(parts)
                else:
                    url = url + "?sz=256"

            return url
        except Exception as e:
            _logger.exception("People API error: %s", e)
            return ""
        
    @http.route("/gmail/auth/start", type="http", auth="user", methods=["GET"])
    def gmail_auth_start(self, **kw):
        _logger.info("🔐 Gmail OAuth flow started from /gmail/auth/start")
        config = request.env["mail.message"].sudo().get_google_config()
        scope = (
            "openid email profile "
            "https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/gmail.send "
            "https://www.googleapis.com/auth/gmail.compose "
            "https://www.googleapis.com/auth/contacts.readonly"
        )
        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "response_type": "code",
            "access_type": "offline",
            "scope": scope,
            "prompt": "consent select_account",
            "include_granted_scopes": "false",
            "login_hint": "",
        }
        auth_url = f'{config["auth_uri"]}?{urllib.parse.urlencode(params)}'
        _logger.info("🔗 Redirecting to Google auth URL: %s", auth_url)
        return redirect(auth_url)

    @http.route("/odoo/gmail/auth/callback", type="http", auth="user", methods=["GET"])
    def gmail_auth_callback(self, **kw):
        _logger.info("📥 Gmail callback received with params: %s", kw)
        code = kw.get("code")
        if not code:
            _logger.error("❌ Missing authorization code in callback.")
            return "Missing code"

        config = request.env["mail.message"].sudo().get_google_config()
        data = {
            "code": code,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "redirect_uri": config["redirect_uri"],
            "grant_type": "authorization_code",
        }

        _logger.info("🔄 Exchanging code for tokens...")
        token_res = requests.post(config["token_uri"], data=data, timeout=10)
        _logger.info("🔄 Requesting token with data: %s", data)

        if token_res.status_code != 200:
            _logger.error("❌ Token exchange failed: %s", token_res.text)
            return request.render(
                "custom_gmail.gmail_auth_error",
                {"error": "Không thể xác thực Gmail. Vui lòng thử lại."},
            )

        token_data = token_res.json()
        _logger.debug("🔐 Token response: %s", json.dumps(token_data, indent=2))

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")

        headers = {"Authorization": f"Bearer {access_token}"}

        # 1) Lấy UserInfo (email + có thể có picture)
        _logger.info("📧 Getting user info from token")
        userinfo_res = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers=headers,
            timeout=10,
        )
        if userinfo_res.status_code != 200:
            _logger.error("UserInfo error %s: %s", userinfo_res.status_code, userinfo_res.text)
            return request.render(
                "custom_gmail.gmail_auth_error",
                {"error": "Không thể xác định thông tin user từ Google."},
            )

        user_info = userinfo_res.json()
        _logger.debug("👤 User Info: %s", json.dumps(user_info, indent=2))
        gmail_email = user_info.get("email")

        # 2) Ưu tiên lấy avatar qua People API (như bạn muốn)
        avatar_url = self._get_google_avatar_from_people(access_token)

        # 3) Fallback cuối: nếu People API không trả, dùng picture của OpenID (nếu có)
        if not avatar_url:
            ui_pic = (user_info or {}).get("picture") or ""
            if ui_pic:
                # tăng size nếu là ảnh Google
                if "lh3.googleusercontent.com" in ui_pic and "sz=" not in ui_pic:
                    sep = "&" if "?" in ui_pic else "?"
                    ui_pic = f"{ui_pic}{sep}sz=256"
                avatar_url = ui_pic

        if not gmail_email:
            _logger.error(
                "❌ Không lấy được Gmail email từ token! UserInfo: %s",
                json.dumps(user_info, indent=2),
            )
            return request.render(
                "custom_gmail.gmail_auth_error",
                {
                    "error": "Không thể xác định email Gmail. Vui lòng thử lại.",
                },
            )

        _logger.info("📌 Gmail authenticated email: %s", gmail_email)

        # Tạo hoặc cập nhật tài khoản Gmail
        account = (
            request.env["gmail.account"]
            .sudo()
            .search(
                [
                    ("user_id", "=", request.env.user.id),
                    ("email", "=", gmail_email),
                ],
                limit=1,
            )
        )

        if not account:
            _logger.info("➕ Creating new Gmail account record")
            account = (
                request.env["gmail.account"]
                .sudo()
                .create(
                    {
                        "user_id": request.env.user.id,
                        "email": gmail_email,
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "token_expiry": datetime.utcnow()
                        + timedelta(seconds=expires_in),
                        "avatar_url": avatar_url,  # ✅ Lưu avatar

                    }
                )
            )
        else:
            _logger.info("♻️ Updating existing Gmail account record")
            account.write(
                {
                    "access_token": access_token,
                    "refresh_token": (
                        refresh_token if refresh_token else account.refresh_token
                    ),
                    "token_expiry": datetime.utcnow() + timedelta(seconds=expires_in),
                    "avatar_url": avatar_url,  # ✅ Lưu avatar

                }
            )

        _logger.info("📬 Fetching Gmail for account ID %s", account.id)
        request.env["mail.message"].sudo().fetch_gmail_for_account(account)
        # request.env["mail.message"].sudo().fetch_gmail_sent_for_account(account)

        _logger.info("✅ Gmail sync complete. Redirecting to OWL UI.")
        return """
            <script>
                window.opener.postMessage("gmail-auth-success", "*");
                window.close();
            </script>
        """

    def sync_messages_and_notifications(self, gmail_messages, account):
        """
        Sync Gmail messages and create notifications.
        """
        current_partner_id = request.env.user.partner_id.id
        # discuss_channel = (
        #     request.env["discuss.channel"]
        #     .sudo()
        #     .search([("name", "=", "Inbox")], limit=1)
        # )

        all_created = True
        for message in gmail_messages:
            try:
                # ⚠️ Bỏ qua nếu đã tồn tại
                existing = self.sudo().search(
                    [("gmail_id", "=", message["id"])], limit=1
                )
                if existing:
                    _logger.info(
                        "Gmail message %s already exists, skipping", message["id"]
                    )
                    continue

                _logger.info("Creating Discuss message for Gmail ID: %s", message["id"])
                created_message = self.sudo().create(
                    {
                        "gmail_id": message["id"],
                        "subject": message["subject"] or "No Subject",
                        "body": message["body"] or "No Body",
                        "message_type": "email",
                        # "model": "discuss.channel",
                        # "res_id": discuss_channel.id,
                        "author_id": current_partner_id,
                        "gmail_account_id": account.id,
                    }
                )

                _logger.info("Creating notification for Gmail ID: %s", message["id"])
                self.env["mail.notification"].sudo().create(
                    {
                        "mail_message_id": created_message.id,
                        "res_partner_id": current_partner_id,
                        "notification_type": "inbox",
                        "is_read": False,
                    }
                )

            except Exception as e:
                _logger.error(
                    "Failed to create Discuss message or notification for Gmail ID: %s. Error: %s",
                    message["id"],
                    str(e),
                )

                all_created = False

        if not all_created:
            raise Exception("Failed to create all Discuss messages or notifications.")
