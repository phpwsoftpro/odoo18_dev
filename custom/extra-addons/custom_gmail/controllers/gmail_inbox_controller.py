# /mnt/extra-addons/.../controllers/gmail_inbox_controller.py
from datetime import timedelta

import base64
import json
import logging
import re
import mimetypes

import requests
from bs4 import BeautifulSoup, Tag
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from email.utils import encode_rfc2231
from email.header import Header

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


def extract_email_only(email_str):
    match = re.search(r"<(.+?)>", email_str)
    return match.group(1) if match else email_str


def _split_addr(addr):
    """split chuỗi địa chỉ bởi , ; hoặc khoảng trắng"""
    return [a.strip() for a in re.split(r"[,\s;]+", addr or "") if a.strip()]


def send_email_with_gmail_api(
    access_token,
    sender_email,
    to_email,
    subject,
    html_content,
    thread_id=None,
    message_id=None,
    headers=None,
):
    message = MIMEMultipart("alternative")
    message["Subject"] = str(Header(subject, "utf-8"))
    message["From"] = sender_email
    message["To"] = to_email

    # ✅ Dùng headers truyền vào nếu có
    if headers:
        for key, value in headers.items():
            message[key] = value
    elif message_id:
        parent_ref = f"<{message_id}>"
        message["In-Reply-To"] = parent_ref
        message["References"] = parent_ref

    html_part = MIMEText(html_content, "html")
    message.attach(html_part)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    api_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    body = {"raw": raw_message}
    if thread_id:
        body["threadId"] = thread_id

    response = requests.post(url, headers=api_headers, json=body)
    _logger.info(
        "📬 Gmail API Response xem Message Id: %s",
        json.dumps(response.json(), indent=2),
    )
    if response.status_code in [200, 202]:
        resp_data = response.json()
        return {
            "status": "success",
            "gmail_id": resp_data.get("id"),
            "thread_id": resp_data.get("threadId"),
            "message_id": resp_data.get("messageId"),
        }
    else:
        _logger.error("Failed to send Gmail: %s", response.text)
        return {
            "status": "error",
            "code": response.status_code,
            "message": response.text,
        }


class GmailInboxController(http.Controller):
    @http.route("/gmail/messages", type="json", auth="user", csrf=False)
    def get_gmail_messages(self, **kwargs):
        account_id = kwargs.get("account_id")
        page = int(kwargs.get("page", 1))
        limit = int(kwargs.get("limit", 15))
        offset = (page - 1) * limit
        label = (kwargs.get("label") or "").upper()

        domain = [("message_type", "=", "email"), ("is_gmail", "=", True)]

        if label == "INBOX":
            domain += [("is_sent_mail", "=", False)]
        elif label == "SENT":
            domain += [("is_sent_mail", "=", True)]
        elif label == "TRASH":
            domain += [("is_deleted", "=", True)]
        elif label == "SPAM":
            domain += [("is_spam", "=", True)]
        elif label == "DRAFT":
            domain += [("is_draft", "=", True)]
        elif label == "STARRED":
            domain += [("is_starred_mail", "=", True)]
        elif label == "ALL_MAIL":
            domain += [("is_draft", "=", False)]
        else:
            domain += [("is_sent_mail", "=", False)]

        if account_id:
            domain.append(("gmail_account_id", "=", int(account_id)))

        total = request.env["mail.message"].sudo().search_count(domain)
        messages = (
            request.env["mail.message"]
            .sudo()
            .search(domain, order="date_received desc", limit=limit, offset=offset)
        )

        result = []
        for msg in messages:
            attachments = (
                request.env["ir.attachment"]
                .sudo()
                .search([("res_model", "=", "mail.message"), ("res_id", "=", msg.id)])
            )
            attachment_list = [
                {
                    "id": att.id,
                    "name": att.name,
                    "url": f"/web/content/{att.id}",
                    "download_url": f"/web/content/{att.id}?download=true",
                    "mimetype": att.mimetype,
                }
                for att in attachments
            ]

            result.append(
                {
                    "id": msg.id,
                    "subject": msg.subject or "No Subject",
                    "sender": msg.email_sender or "Unknown Sender",
                    "to": extract_email_only(msg.email_sender or ""),
                    "receiver": msg.email_receiver or "Unknown Receiver",
                    "date_received": (
                        msg.date_received.strftime("%Y-%m-%d %H:%M:%S")
                        if msg.date_received
                        else ""
                    ),
                    "body": msg.body,
                    "attachments": attachment_list,
                    "thread_id": msg.thread_id or "",
                    "message_id": msg.message_id or "",
                    "is_read": msg.is_read,
                    "is_starred_mail": msg.is_starred_mail,
                    "avatar_url": msg.avatar_url,
                    "labels": (msg.gmail_labels or "").split(",") if msg.gmail_labels else [],
                }
            )

        return {"messages": result, "total": total}

    @http.route("/gmail/all_mail_messages", type="json", auth="user", csrf=False)
    def get_gmail_all_mail_messages(self, **kwargs):
        account_id = kwargs.get("account_id")
        page = int(kwargs.get("page", 1))
        limit = int(kwargs.get("limit", 15))
        offset = (page - 1) * limit

        domain = [
            ("message_type", "=", "email"),
            ("is_gmail", "=", True),
            ("is_draft_mail", "!=", True),
        ]
        if account_id:
            domain.append(("gmail_account_id", "=", int(account_id)))

        total = request.env["mail.message"].sudo().search_count(domain)
        messages = (
            request.env["mail.message"]
            .sudo()
            .search(domain, order="date_received desc", limit=limit, offset=offset)
        )

        result = []
        for msg in messages:
            attachments = (
                request.env["ir.attachment"]
                .sudo()
                .search([("res_model", "=", "mail.message"), ("res_id", "=", msg.id)])
            )
            attachment_list = [
                {
                    "id": att.id,
                    "name": att.name,
                    "url": f"/web/content/{att.id}",
                    "download_url": f"/web/content/{att.id}?download=true",
                    "mimetype": att.mimetype,
                }
                for att in attachments
            ]

            result.append(
                {
                    "id": msg.id,
                    "subject": msg.subject or "No Subject",
                    "sender": msg.email_sender or "Unknown Sender",
                    "to": extract_email_only(msg.email_sender or ""),
                    "receiver": msg.email_receiver or "Unknown Receiver",
                    "cc": msg.email_cc or "",
                    "date_received": (
                        msg.date_received.strftime("%Y-%m-%d %H:%M:%S")
                        if msg.date_received
                        else ""
                    ),
                    "body": msg.body,
                    "attachments": attachment_list,
                    "thread_id": msg.thread_id or "",
                    "message_id": msg.message_id or "",
                    "is_read": msg.is_read,
                    "is_starred_mail": msg.is_starred_mail,
                    "is_sent_mail": msg.is_sent_mail,
                    "labels": (msg.gmail_labels or "").split(",") if msg.gmail_labels else [],
                }
            )

        return {"messages": result, "total": total}

    @http.route("/gmail/sent_messages", type="json", auth="user", csrf=False)
    def get_gmail_sent_messages(self, **kwargs):
        account_id = kwargs.get("account_id")
        page = int(kwargs.get("page", 1))
        limit = int(kwargs.get("limit", 15))
        offset = (page - 1) * limit

        domain = [
            ("message_type", "=", "email"),
            ("is_gmail", "=", True),
            ("is_sent_mail", "=", True),
        ]
        if account_id:
            domain.append(("gmail_account_id", "=", int(account_id)))

        total = request.env["mail.message"].sudo().search_count(domain)
        messages = (
            request.env["mail.message"]
            .sudo()
            .search(domain, order="date_received desc", limit=limit, offset=offset)
        )

        result = []
        for msg in messages:
            full_body = msg.body
            attachments = (
                request.env["ir.attachment"]
                .sudo()
                .search([("res_model", "=", "mail.message"), ("res_id", "=", msg.id)])
            )
            attachment_list = [
                {
                    "id": att.id,
                    "name": att.name,
                    "url": f"/web/content/{att.id}",
                    "download_url": f"/web/content/{att.id}?download=true",
                    "mimetype": att.mimetype,
                }
                for att in attachments
            ]
            result.append(
                {
                    "id": msg.id,
                    "subject": msg.subject or "No Subject",
                    "sender": msg.email_sender or "Unknown Sender",
                    "to": extract_email_only(msg.email_sender or ""),
                    "receiver": msg.email_receiver or "Unknown Receiver",
                    "date_received": (
                        msg.date_received.strftime("%Y-%m-%d %H:%M:%S")
                        if msg.date_received
                        else ""
                    ),
                    "body": full_body,
                    "attachments": attachment_list,
                    "thread_id": msg.thread_id or "",
                    "message_id": msg.message_id or "",
                    "avatar_url": msg.avatar_url,
                    "labels": (msg.gmail_labels or "").split(",") if msg.gmail_labels else [],
                }
            )

        return {"messages": result, "total": total}

    @http.route("/gmail/draft_messages", type="json", auth="user", csrf=False)
    def get_gmail_draft_messages(self, **kwargs):
        account_id = kwargs.get("account_id")
        page = int(kwargs.get("page", 1))
        limit = int(kwargs.get("limit", 15))
        offset = (page - 1) * limit

        domain = [
            ("message_type", "=", "email"),
            ("is_gmail", "=", True),
            ("is_draft_mail", "=", True),
        ]
        if account_id:
            domain.append(("gmail_account_id", "=", int(account_id)))

        total = request.env["mail.message"].sudo().search_count(domain)
        messages = (
            request.env["mail.message"]
            .sudo()
            .search(domain, order="date_received desc", limit=limit, offset=offset)
        )

        result = []
        for msg in messages:
            full_body = msg.body
            attachments = (
                request.env["ir.attachment"]
                .sudo()
                .search([("res_model", "=", "mail.message"), ("res_id", "=", msg.id)])
            )
            attachment_list = [
                {
                    "id": att.id,
                    "name": att.name,
                    "url": f"/web/content/{att.id}",
                    "download_url": f"/web/content/{att.id}?download=true",
                    "mimetype": att.mimetype,
                }
                for att in attachments
            ]
            result.append(
                {
                    "id": msg.id,
                    "subject": msg.subject or "No Subject",
                    "sender": msg.email_sender or "Unknown Sender",
                    "to": extract_email_only(msg.email_sender or ""),
                    "receiver": msg.email_receiver or "Unknown Receiver",
                    "date_received": (
                        msg.date_received.strftime("%Y-%m-%d %H:%M:%S")
                        if msg.date_received
                        else ""
                    ),
                    "body": full_body,
                    "attachments": attachment_list,
                    "thread_id": msg.thread_id or "",
                    "message_id": msg.message_id or "",
                    "labels": (msg.gmail_labels or "").split(",") if msg.gmail_labels else [],
                }
            )

        return {"messages": result, "total": total}

    @http.route("/gmail/starred_messages", type="json", auth="user", csrf=False)
    def get_gmail_starred_messages(self, **kwargs):
        account_id = kwargs.get("account_id")
        page = int(kwargs.get("page", 1))
        limit = int(kwargs.get("limit", 15))
        offset = (page - 1) * limit

        domain = [
            ("message_type", "=", "email"),
            ("is_gmail", "=", True),
            ("is_starred_mail", "=", True),
        ]
        if account_id:
            domain.append(("gmail_account_id", "=", int(account_id)))

        total = request.env["mail.message"].sudo().search_count(domain)
        messages = (
            request.env["mail.message"]
            .sudo()
            .search(domain, order="date_received desc", limit=limit, offset=offset)
        )

        result = []
        for msg in messages:
            attachments = (
                request.env["ir.attachment"]
                .sudo()
                .search([("res_model", "=", "mail.message"), ("res_id", "=", msg.id)])
            )
            attachment_list = [
                {
                    "id": att.id,
                    "name": att.name,
                    "url": f"/web/content/{att.id}",
                    "download_url": f"/web/content/{att.id}?download=true",
                    "mimetype": att.mimetype,
                }
                for att in attachments
            ]

            result.append(
                {
                    "id": msg.id,
                    "subject": msg.subject or "No Subject",
                    "sender": msg.email_sender or "Unknown Sender",
                    "to": extract_email_only(msg.email_sender or ""),
                    "receiver": msg.email_receiver or "Unknown Receiver",
                    "date_received": (
                        msg.date_received.strftime("%Y-%m-%d %H:%M:%S")
                        if msg.date_received
                        else ""
                    ),
                    "body": msg.body,
                    "attachments": attachment_list,
                    "thread_id": msg.thread_id or "",
                    "message_id": msg.message_id or "",
                    "is_read": msg.is_read,
                    "is_starred_mail": msg.is_starred_mail,
                    "labels": (msg.gmail_labels or "").split(",") if msg.gmail_labels else [],
                }
            )

        return {"messages": result, "total": total}

    @staticmethod
    def clean_gmail_body(html_content):
        soup = BeautifulSoup(html_content or "", "lxml")
        for tag in soup(["style", "script"]):
            tag.decompose()
        return soup.get_text(separator="\n").strip()

    @http.route("/gmail/current_user_info", type="json", auth="user")
    def current_user_info(self, **kwargs):
        accounts = (
            request.env["gmail.account"]
            .sudo()
            .search(
                [("user_id", "=", request.env.user.id)],
                order="write_date desc",
                limit=1,
            )
        )

        if not accounts:
            return {"status": "error", "message": "No Gmail accounts found"}

        return {"status": "success", "email": accounts[0].email}

    @http.route("/gmail/account_id_by_email", type="json", auth="user")
    def get_account_id(self, email):
        account = (
            request.env["gmail.account"]
            .sudo()
            .search(
                [("email", "=", email), ("user_id", "=", request.env.user.id)], limit=1
            )
        )
        return {"account_id": account.id if account else False}

    @http.route("/gmail/refresh_mail", type="json", auth="user", csrf=False)
    def refresh_mail(self, **kwargs):
        account_id = kwargs.get("account_id")
        if not account_id:
            _logger.warning("❌ Thiếu account_id trong request")
            return {"status": "fail", "error": "Thiếu account_id"}

        try:
            _logger.info(
                "📥 [START] Đã nhận refresh request cho account_id = %s", account_id
            )

            account = request.env["gmail.account"].sudo().browse(int(account_id))
            if not account.exists():
                _logger.warning("❌ Không tìm thấy tài khoản với ID %s", account_id)
                return {"status": "fail", "error": "Account không tồn tại"}

            result_inbox = request.env["mail.message"].fetch_gmail_for_account(account)
            result_sent = request.env["mail.message"].fetch_gmail_sent_for_account(
                account
            )
            result_draft = request.env["mail.message"].fetch_gmail_drafts_for_account(
                account
            )
            result_starred = request.env[
                "mail.message"
            ].fetch_gmail_starred_for_account(account)
            _logger.info("✅ [DONE] Refresh xong cho account_id = %s", account_id)
            return {
                "status": (
                    "ok"
                    if (
                        result_inbox and result_sent and result_draft and result_starred
                    )
                    else "fail"
                )
            }

        except Exception as e:
            _logger.exception(
                "❌ Lỗi khi xử lý refresh_mail cho account_id = %s", account_id
            )
            return {"status": "fail", "error": str(e)}

    @http.route("/gmail/sync_account", type="json", auth="user")
    def sync_gmail_by_account(self, account_id):
        account = request.env["gmail.account"].sudo().browse(int(account_id))
        request.env["mail.message"].sudo().fetch_gmail_for_account(account)
        request.env["mail.message"].sudo().fetch_gmail_sent_for_account(account)
        request.env["mail.message"].sudo().fetch_gmail_drafts_for_account(account)
        request.env["mail.message"].sudo().fetch_gmail_starred_for_account(account)
        return {"status": "ok"}

    @http.route("/gmail/save_account", type="json", auth="user", csrf=False)
    def save_gmail_account(self, email, **kwargs):
        user_id = request.env.user.id
        GmailAccount = request.env["gmail.account"].sudo()

        existing = GmailAccount.search(
            [("email", "=", email), ("user_id", "=", user_id)], limit=1
        )
        if not existing:
            GmailAccount.create({"user_id": user_id, "email": email})

        return {"status": "saved"}

    @http.route("/gmail/my_accounts", type="json", auth="user")
    def my_gmail_accounts(self):
        accounts = (
            request.env["gmail.account"]
            .sudo()
            .search(
                [("user_id", "=", request.env.user.id), ("access_token", "!=", False)]
            )
        )
        return [
            {
                "id": acc.id,
                "email": acc.email,
                "name": (acc.email or "").split("@")[0] if acc.email else "Unknown",
                "initial": (acc.email or "X")[0].upper(),
                "status": "active",
                "type": "gmail",
            }
            for acc in accounts
        ]

    @http.route("/gmail/session/ping", type="json", auth="user")
    def ping(self, account_id):
        _logger.warning(
            f"📥 [PING] Nhận account_id: {account_id} (type={type(account_id)})"
        )

        try:
            account_id = int(account_id)
        except Exception as e:
            _logger.error(f"❌ account_id không thể ép kiểu int: {account_id} ({e})")
            return {"error": "account_id không hợp lệ"}

        account = request.env["gmail.account"].sudo().browse(account_id)
        if not account.exists():
            _logger.warning(f"📥 [PING] Gmail account {account_id} not found")
            return {"error": "account not found"}

        user_id = request.env.user.id
        _logger.warning(
            f"📥 [PING] Đang tạo session với gmail_account_id={account.id}, user_id={user_id}"
        )

        session_model = request.env["gmail.account.session"].sudo()
        session = session_model.search(
            [("gmail_account_id", "=", account.id), ("user_id", "=", user_id)], limit=1
        )

        now = fields.Datetime.now()

        if session:
            session.write({"last_ping": now})
            _logger.info(f"🔄 [PING] Đã cập nhật last_ping cho session ID {session.id}")
        else:
            _logger.info("🆕 [PING] Chưa có session → tạo mới")
            try:
                created = session_model.create(
                    {
                        "gmail_account_id": account.id,
                        "user_id": user_id,
                        "last_ping": now,
                    }
                )
                _logger.info(f"✅ [PING] Đã tạo session ID {created.id}")
            except Exception as e:
                _logger.critical(
                    f"🔥 [PING] Lỗi khi tạo session! gmail_account_id={account.id}, user_id={user_id} ➤ {e}"
                )
                raise

        return {"has_new_mail": account.has_new_mail}

    @http.route("/gmail/clear_new_mail_flag", type="json", auth="user")
    def clear_flag(self, account_id):
        account = request.env["gmail.account"].sudo().browse(int(account_id))
        account.has_new_mail = False
        _logger.info(f"✅ CLEAR FLAG: Reset has_new_mail on {account.email}")
        return {"status": "ok"}

    @http.route("/gmail/delete_account", type="json", auth="user", csrf=False)
    def delete_account(self, account_id):
        account = (
            request.env["gmail.account"]
            .sudo()
            .search(
                [("id", "=", account_id), ("user_id", "=", request.env.user.id)],
                limit=1,
            )
        )

        if not account:
            return {"status": "not_found"}

        messages = (
            request.env["mail.message"]
            .sudo()
            .search(
                [
                    ("model", "=", "gmail.account"),
                    ("res_id", "=", account.id),
                    ("is_gmail", "=", True),
                ]
            )
        )

        attachments = (
            request.env["ir.attachment"]
            .sudo()
            .search(
                [("res_model", "=", "mail.message"), ("res_id", "in", messages.ids)]
            )
        )
        attachments.unlink()

        request.env["mail.notification"].sudo().search(
            [("mail_message_id", "in", messages.ids)]
        ).unlink()
        messages.unlink()

        request.env["gmail.account.sync.state"].sudo().search(
            [("gmail_account_id", "=", account.id)]
        ).unlink()

        account.write(
            {"access_token": False, "refresh_token": False, "token_expiry": False}
        )

        return {"status": "token_removed"}

    @http.route("/gmail/mark_as_read", type="json", auth="user", csrf=False)
    def mark_email_as_read(self, message_id):
        domain = [("id", "=", message_id)]
        if not str(message_id).isdigit():
            domain = [("message_id", "=", message_id)]

        msg = request.env["mail.message"].sudo().search(domain, limit=1)
        if msg and not msg.is_read:
            msg.write({"is_read": True})
        return {"status": "ok"}

    @http.route("/gmail/set_star", type="json", auth="user", csrf=False)
    def set_star(self, **kwargs):
        _logger.warning("✅ Received kwargs: %s", kwargs)
        id = kwargs.get("id")
        starred = kwargs.get("starred")

        if not id:
            return {"status": "error", "message": "Missing id"}

        message = request.env["mail.message"].sudo().browse(int(id))
        if message.exists():
            message.is_starred_mail = starred
            return {"status": "ok", "id": id, "starred": starred}
        else:
            return {"status": "not_found", "id": id}
    
    @http.route('/gmail/delete_message', type='json', auth='user', csrf=False)
    def delete_message(self, message_id=None, **kw):
        # --- Validate và chuẩn hóa ID ---
        if not message_id:
            return {"success": False, "error": "No message_id provided"}
        ids = isinstance(message_id, list) and message_id or [message_id]
        try:
            ids = [int(x) for x in ids]
        except ValueError:
            return {"success": False, "error": "Invalid message_id"}

        # --- Xử lý từng thư ---
        for mid in ids:
            msg = request.env['mail.message'].sudo().browse(mid)
            if not msg.exists() or not msg.gmail_id:
                continue

            acct = msg.gmail_account_id.sudo()
            # Refresh token nếu hết hạn
            now = fields.Datetime.now()
            if acct.token_expiry and acct.token_expiry < now:
                acct.refresh_access_token()

            token = acct.access_token
            trash_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg.gmail_id}/trash"
            try:
                resp = requests.post(
                    trash_url,
                    headers={"Authorization": f"Bearer {token}"}
                )
            except Exception as e:
                _logger.error("HTTP request failed: %s", e)
                return {"success": False, "error": str(e)}

            if resp.status_code == 401:
                # Nếu 401, thử refresh lần nữa và retry
                acct.refresh_access_token()
                token = acct.access_token
                resp = requests.post(
                    trash_url,
                    headers={"Authorization": f"Bearer {token}"}
                )

            if resp.status_code != 200:
                _logger.error("Gmail trash failed %s: %s", resp.status_code, resp.text)
                return {"success": False, "error": f"Gmail trash HTTP {resp.status_code}"}

            _logger.info("Moved Gmail ID %s to Trash (HTTP)", msg.gmail_id)

            # Xóa attachments & notification
            request.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'mail.message'),
                ('res_id', '=', msg.id),
            ]).unlink()
            request.env['mail.notification'].sudo().search([
                ('mail_message_id', '=', msg.id),
            ]).unlink()

            # Xóa record Odoo
            msg.unlink()

        return {"success": True, "deleted_ids": ids}


class UploadController(http.Controller):
    @http.route(
        "/custom_gmail/upload_image",
        type="http",
        auth="user",
        csrf=False,
        methods=["POST"],
    )
    def upload_image_base64(self, **kwargs):
        upload = request.httprequest.files.get("upload")
        if upload:
            data = base64.b64encode(upload.read()).decode("utf-8")
            mimetype = upload.content_type
            return request.make_json_response({"url": f"data:{mimetype};base64,{data}"})
        return request.make_json_response({"error": "No file"}, status=400)

    @http.route("/custom_gmail/upload_image", type="http", auth="user", csrf=False)
    def upload_image(self, **kwargs):
        upload = request.httprequest.files.get("upload")
        if not upload:
            return json.dumps({"error": "No file"})

        attachment = (
            request.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": upload.filename,
                    "datas": base64.b64encode(upload.read()),
                    "res_model": "mail.compose.message",
                    "mimetype": upload.content_type,
                }
            )
        )

        return json.dumps({"url": f"/web/content/{attachment.id}?download=true"})


class MailAPIController(http.Controller):
    @http.route(
        "/api/send_email", type="http", auth="user", csrf=False, methods=["POST"]
    )
    def send_email(self, **kwargs):
        # ---- Lấy form ----
        form = request.httprequest.form
        to = (form.get("to") or "").strip()
        cc = (form.get("cc") or "").strip()
        bcc = (form.get("bcc") or "").strip()
        subject = (form.get("subject") or "").strip()
        body_html = (form.get("body_html") or "").strip()
        thread_id = form.get("thread_id")
        message_id = form.get("message_id")
        account_id = form.get("account_id")
        provider = form.get("provider", "gmail")

        # Người nhận: cho phép chỉ Cc/Bcc
        all_rcpts = _split_addr(to) + _split_addr(cc) + _split_addr(bcc)
        if not all_rcpts:
            return request.make_json_response(
                {"status": "error", "message": "Thiếu người nhận (To/Cc/Bcc)"},
                status=400,
            )

        files = request.httprequest.files.getlist("attachments[]")
        has_attachments = bool(files)
        has_body = bool(body_html)

        if not subject and (has_body or has_attachments):
            subject = "No Subject"
        if not subject and not has_body and not has_attachments:
            return request.make_json_response(
                {
                    "status": "error",
                    "message": "Missing subject, body, and attachments",
                },
                status=400,
            )

        # ---- Inline manifest cho CID ----
        inline_manifest_raw = form.get("inline_manifest") or "[]"
        try:
            inline_manifest = json.loads(inline_manifest_raw)
        except Exception:
            inline_manifest = []
        inline_map = {
            it.get("name"): it
            for it in inline_manifest
            if it.get("name") and it.get("cid")
        }

        # ---- Chuẩn bị MIME parts từ file upload ----
        attachments = []  # parts "attachment"
        inlines = []  # parts "inline" (Content-ID)
        for fs in files:
            content = fs.read()
            fs.seek(0)
            fname = fs.filename or "file"
            # inline ?
            if fname in inline_map:
                im = inline_map[fname]
                mt = im.get("mimetype") or (
                    mimetypes.guess_type(fname)[0] or "application/octet-stream"
                )
                maintype, subtype = (mt.split("/", 1) + ["octet-stream"])[:2]
                if maintype == "image":
                    part = MIMEImage(content, _subtype=subtype)
                else:
                    part = MIMEBase(maintype, subtype)
                    part.set_payload(content)
                    encoders.encode_base64(part)
                part.add_header("Content-ID", f"<{im['cid']}>")
                part.add_header(
                    "Content-Disposition",
                    "inline",
                    **{"filename*": encode_rfc2231(fname, "utf-8")},
                )
                inlines.append(part)
            else:
                # ✅ đoán đúng Content-Type cho mọi tệp
                ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
                maintype, subtype = (ctype.split("/", 1) + ["octet-stream"])[:2]
                part = MIMEBase(maintype, subtype)
                part.set_payload(content)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    **{"filename*": encode_rfc2231(fname, "utf-8")},
                )
                attachments.append(part)

        # ---- Outlook ----
        if provider == "outlook":
            acct = request.env["outlook.account"].sudo().browse(int(account_id))
            if not acct.exists():
                return request.make_json_response(
                    {"status": "error", "message": "Invalid Outlook account"},
                    status=400,
                )

            token = acct.outlook_access_token
            refresh_token = acct.outlook_refresh_token

            def _send(token_use):
                send_url = "https://graph.microsoft.com/v1.0/me/sendMail"

                def _mk_rcpts(lst):
                    return [{"emailAddress": {"address": a}} for a in _split_addr(lst)]

                message = {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": body_html},
                }
                to_list = _split_addr(to)
                cc_list = _split_addr(cc)
                bcc_list = _split_addr(bcc)
                if to_list:
                    message["toRecipients"] = _mk_rcpts(to_list)
                if cc_list:
                    message["ccRecipients"] = _mk_rcpts(cc_list)
                if bcc_list:
                    message["bccRecipients"] = _mk_rcpts(bcc_list)

                if attachments or inlines:
                    message["attachments"] = []
                    # Outlook không hỗ trợ CID như Gmail trong payload đơn giản này,
                    # nên inline cũng gửi như file đính kèm (tuỳ nhu cầu có thể dùng MIME raw qua /sendMail?).
                    for part in attachments + inlines:
                        file_content = part.get_payload(decode=True)
                        message["attachments"].append(
                            {
                                "@odata.type": "#microsoft.graph.fileAttachment",
                                "name": part.get_filename() or "file",
                                "contentBytes": base64.b64encode(file_content).decode(
                                    "utf-8"
                                ),
                                "contentType": part.get_content_type(),
                                # Không set contentId/contentDisposition vì Graph API dạng fileAttachment
                            }
                        )
                payload = {"message": message, "saveToSentItems": "true"}
                return requests.post(
                    send_url,
                    headers={
                        "Authorization": f"Bearer {token_use}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

            resp = _send(token)
            if resp.status_code == 401 and refresh_token:
                cfg = request.env["outlook.mail.sync"].sudo().get_outlook_config()
                token_resp = requests.post(
                    "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                    data={
                        "client_id": cfg["client_id"],
                        "client_secret": cfg["client_secret"],
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "redirect_uri": cfg["redirect_uri"],
                        "scope": "https://graph.microsoft.com/.default",
                    },
                )
                if token_resp.status_code == 200:
                    tj = token_resp.json()
                    new_token = tj.get("access_token")
                    new_refresh = tj.get("refresh_token")
                    if new_token:
                        acct.write(
                            {
                                "outlook_access_token": new_token,
                                "outlook_refresh_token": new_refresh or refresh_token,
                            }
                        )
                        resp = _send(new_token)
                    else:
                        return request.make_json_response(
                            {"status": "error", "message": "Cannot refresh token"},
                            status=401,
                        )
                else:
                    return request.make_json_response(
                        {"status": "error", "message": "Outlook token expired"},
                        status=401,
                    )

            if resp.status_code in (200, 202):
                return request.make_json_response({"status": "success"})
            else:
                return request.make_json_response(
                    {"status": "error", "code": resp.status_code, "message": resp.text},
                    status=200,
                )

        # ---- Gmail ----
        acct = request.env["gmail.account"].sudo().browse(int(account_id))
        if not acct.exists():
            return request.make_json_response(
                {"status": "error", "message": "Invalid Gmail account"},
                status=400,
            )

        now = fields.Datetime.now()
        token = acct.access_token
        if not token or (acct.token_expiry and acct.token_expiry < now):
            _logger.info("🔄 Refreshing Gmail access token…")
            config = request.env["mail.message"].sudo().get_google_config()
            resp = requests.post(
                config["token_uri"],
                data={
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "refresh_token": acct.refresh_token,
                    "grant_type": "refresh_token",
                }
            )

            resp.raise_for_status()
            tok = resp.json()
            token = tok.get("access_token")
            if not token:
                return request.make_json_response(
                    {"status": "error", "message": "Failed to refresh token"},
                    status=500,
                )
            vals = {"access_token": token}
            if tok.get("expires_in"):
                expiry = now + timedelta(seconds=int(tok["expires_in"]))
                vals["token_expiry"] = fields.Datetime.to_string(expiry)
            acct.sudo().write(vals)

        sender_email = acct.email

        # ---- Xây MIME: mixed (attachments) + related (html + inline) ----
        root = MIMEMultipart("mixed")
        if _split_addr(to):
            root["To"] = to
        if _split_addr(cc):
            root["Cc"] = cc
        if _split_addr(bcc):
            root["Bcc"] = bcc
        root["From"] = sender_email
        root["Subject"] = subject
        if message_id:
            root["In-Reply-To"] = f"<{message_id}>"
            root["References"] = f"<{message_id}>"

        related = MIMEMultipart("related")
        related.attach(MIMEText(body_html, "html"))

        # gắn inline trước
        for p in inlines:
            related.attach(p)
        root.attach(related)

        # sau đó gắn file đính kèm
        for p in attachments:
            root.attach(p)

        _logger.info("📤 [SEND_EMAIL] Gmail message format:")
        _logger.info("From: %s", sender_email)
        _logger.info("To: %s | Cc: %s | Bcc: %s", to, cc, bcc)
        _logger.info("Subject: %s", subject)
        _logger.debug("Full MIME message:\n%s", root.as_string())

        raw_str = base64.urlsafe_b64encode(root.as_bytes()).decode()

        send_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
        payload = {"raw": raw_str}
        if thread_id:
            payload["threadId"] = thread_id

        resp = requests.post(
            send_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

        if resp.status_code == 404 and thread_id:
            _logger.warning("⚠️ Thread %s not found, retry without threadId", thread_id)
            payload.pop("threadId", None)
            resp = requests.post(
                send_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if resp.status_code in (200, 202):
            gmail_id = resp.json().get("id")
            result = {"status": "success", "gmail_id": gmail_id}
            _logger.info("✅ Gmail sent message id=%s", gmail_id)
        else:
            result = {"status": "error", "code": resp.status_code, "message": resp.text}
            _logger.error("❌ Gmail send error: %s", resp.text)

        _logger.info("📤 Gmail API response: %s", result)
        return request.make_json_response(result)

    @http.route(
        "/api/save_draft", type="http", auth="user", csrf=False, methods=["POST"]
    )
    def save_draft(self, **kwargs):
        """Save the composed email as a Gmail/Outlook draft"""
        raw_data = request.httprequest.get_data(as_text=True)
        _logger.info("📥 [save_draft] Raw data: %s", raw_data)
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            _logger.error("❌ [save_draft] Invalid JSON")
            return request.make_json_response(
                {"status": "error", "message": "Invalid JSON"}, status=400
            )

        to = (data.get("to") or "").strip()
        cc = (data.get("cc") or "").strip()
        bcc = (data.get("bcc") or "").strip()
        subject = data.get("subject", "")
        body_html = data.get("body_html") or data.get("body", "")
        thread_id = data.get("thread_id")
        message_id = data.get("message_id")
        account_id = data.get("account_id")
        provider = data.get("provider", "gmail")
        draft_id = data.get("draft_id")

        if not account_id:
            _logger.warning("❌ [save_draft] Missing account_id")
            return request.make_json_response(
                {"status": "error", "message": "Missing account_id"}, status=400
            )

        if provider == "outlook":
            acct = request.env["outlook.account"].sudo().browse(int(account_id))
        else:
            acct = request.env["gmail.account"].sudo().browse(int(account_id))
        if not acct.exists():
            _logger.error(
                "❌ [save_draft] %s account %s not found", provider, account_id
            )
            return request.make_json_response(
                {"status": "error", "message": "Invalid account"}, status=400
            )

        now = fields.Datetime.now()
        if provider == "outlook":
            token = acct.outlook_access_token
            refresh_token = acct.outlook_refresh_token
        else:
            token = acct.access_token

        if provider == "gmail" and (
            not token or (acct.token_expiry and acct.token_expiry < now)
        ):
            _logger.info("🔄 [save_draft] Refreshing Gmail token")
            config = request.env["mail.message"].sudo().get_google_config()
            resp = requests.post(
                config["token_uri"],
                data={
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "refresh_token": acct.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if resp.status_code != 200:
                _logger.error("❌ [save_draft] Token refresh failed: %s", resp.text)
                return request.make_json_response(
                    {"status": "error", "message": "Failed to refresh token"},
                    status=401,
                )
            tk = resp.json()
            token = tk.get("access_token")
            vals = {"access_token": token}
            if tk.get("expires_in"):
                expiry = now + timedelta(seconds=int(tk["expires_in"]))
                vals["token_expiry"] = fields.Datetime.to_string(expiry)
            acct.sudo().write(vals)
        elif provider == "outlook" and not token:
            _logger.info("🔄 [save_draft] Refreshing Outlook token")
            cfg = request.env["outlook.mail.sync"].sudo().get_outlook_config()
            resp = requests.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "redirect_uri": cfg["redirect_uri"],
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            if resp.status_code == 200:
                tj = resp.json()
                token = tj.get("access_token")
                acct.write(
                    {
                        "outlook_access_token": token,
                        "outlook_refresh_token": tj.get("refresh_token")
                        or refresh_token,
                    }
                )
            else:
                return request.make_json_response(
                    {"status": "error", "message": "Outlook token expired"},
                    status=401,
                )

        if provider == "gmail":
            # set header To/Cc/Bcc vào draft
            mime_msg = MIMEMultipart()
            if _split_addr(to):
                mime_msg["to"] = to
            if _split_addr(cc):
                mime_msg["Cc"] = cc
            if _split_addr(bcc):
                mime_msg["Bcc"] = bcc
            mime_msg["from"] = acct.email
            mime_msg["subject"] = subject
            if message_id:
                mime_msg["In-Reply-To"] = f"<{message_id}>"
                mime_msg["References"] = f"<{message_id}>"
            mime_msg.attach(MIMEText(body_html, "html"))

            raw_str = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
            try:
                if draft_id:
                    draft_url = f"https://gmail.googleapis.com/gmail/v1/users/me/drafts/{draft_id}"
                    payload = {"id": draft_id, "message": {"raw": raw_str}}
                    if thread_id:
                        payload["message"]["threadId"] = thread_id
                    resp = requests.put(
                        draft_url,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                else:
                    draft_url = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
                    payload = {"message": {"raw": raw_str}}
                    if thread_id:
                        payload["message"]["threadId"] = thread_id
                    resp = requests.post(
                        draft_url,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
            except requests.exceptions.RequestException as req_err:
                _logger.error("❌ [save_draft] Gmail request failed: %s", req_err)
                return request.make_json_response(
                    {"status": "error", "message": str(req_err)}, status=500
                )

            if 200 <= resp.status_code < 300:
                try:
                    dr = resp.json()
                except ValueError:
                    dr = {}
                _logger.info("✅ [save_draft] Draft saved, id=%s", dr.get("id"))
                try:
                    request.env["mail.message"].sudo().fetch_gmail_drafts_for_account(
                        acct
                    )
                except Exception as fetch_err:
                    _logger.warning(
                        "⚠️ [save_draft] Failed to fetch drafts: %s", fetch_err
                    )
                return request.make_json_response(
                    {"status": "success", "draft_id": dr.get("id")}
                )
            _logger.error(
                "❌ [save_draft] Gmail API error %s: %s", resp.status_code, resp.text
            )
            if (
                resp.status_code == 403
                and "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in resp.text
            ):
                _logger.error(
                    "🚫 [save_draft] Missing compose scope. User must reauthorize Gmail."
                )
                acct.sudo().write({"access_token": False, "token_expiry": False})
            return request.make_json_response(
                {"status": "error", "code": resp.status_code, "message": resp.text},
                status=200,
            )
        else:

            def _request(tok):
                url = "https://graph.microsoft.com/v1.0/me/messages"
                method = requests.post
                if draft_id:
                    url = f"https://graph.microsoft.com/v1.0/me/messages/{draft_id}"
                    method = requests.patch

                def _mk_rcpts(lst):
                    return [{"emailAddress": {"address": a}} for a in _split_addr(lst)]

                message = {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": body_html},
                }
                if _split_addr(to):
                    message["toRecipients"] = _mk_rcpts(to)
                if _split_addr(cc):
                    message["ccRecipients"] = _mk_rcpts(cc)
                if _split_addr(bcc):
                    message["bccRecipients"] = _mk_rcpts(bcc)
                return method(
                    url,
                    headers={
                        "Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json",
                    },
                    json=message,
                )

            try:
                resp = _request(token)
            except requests.exceptions.RequestException as req_err:
                _logger.error("❌ [save_draft] Outlook request failed: %s", req_err)
                return request.make_json_response(
                    {"status": "error", "message": str(req_err)}, status=500
                )
            if resp.status_code == 401 and refresh_token:
                cfg = request.env["outlook.mail.sync"].sudo().get_outlook_config()
                tk_resp = requests.post(
                    "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                    data={
                        "client_id": cfg["client_id"],
                        "client_secret": cfg["client_secret"],
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "redirect_uri": cfg["redirect_uri"],
                        "scope": "https://graph.microsoft.com/.default",
                    },
                )
                if tk_resp.status_code == 200:
                    tk_j = tk_resp.json()
                    token = tk_j.get("access_token")
                    acct.write(
                        {
                            "outlook_access_token": token,
                            "outlook_refresh_token": tk_j.get("refresh_token")
                            or refresh_token,
                        }
                    )
                    resp = _request(token)
                else:
                    return request.make_json_response(
                        {"status": "error", "message": "Outlook token expired"},
                        status=401,
                    )

            if 200 <= resp.status_code < 300:
                try:
                    dr = resp.json()
                except ValueError:
                    dr = {}
                return request.make_json_response(
                    {"status": "success", "draft_id": dr.get("id", draft_id)}
                )
            if resp.status_code == 403:
                _logger.error("🚫 [save_draft] Outlook access denied: %s", resp.text)
                acct.sudo().write(
                    {"outlook_access_token": False, "outlook_refresh_token": False}
                )
                return request.make_json_response(
                    {"status": "error", "code": 403, "message": resp.text}, status=200
                )
            return request.make_json_response(
                {"status": "error", "code": resp.status_code, "message": resp.text},
                status=200,
            )

    @http.route("/gmail/analyze", type="json", auth="user", csrf=False)
    def analyze_message(self, message_id, analysis_text):
        message = request.env["mail.message"].sudo().browse(int(message_id))
        if not message.exists():
            return {"status": "error", "message": "Message not found"}
        res = message.action_analyze(analysis_text)
        return {"status": "ok", "lead_id": res.get("lead_id")}

    @http.route("/gmail/debug_token", type="json", auth="user", csrf=False)
    def get_gmail_access_token(self):
        account = (
            request.env["gmail.account"]
            .sudo()
            .search([("user_id", "=", request.env.user.id)], limit=1)
        )
        if not account:
            return {"error": "Không tìm thấy tài khoản Gmail"}
        return {
            "access_token": account.access_token,
            "email": account.email,
            "expires": str(account.token_expiry),
        }

    @http.route("/gmail/thread_detail", type="json", auth="user", csrf=False)
    def get_thread_detail(self, thread_id=None, account_id=None):
        if not thread_id:
            return {"status": "error", "message": "Missing thread_id"}

        domain = [
            ("message_type", "=", "email"),
            ("is_gmail", "=", True),
            ("thread_id", "=", thread_id),
        ]
        if account_id:
            domain.append(("gmail_account_id", "=", int(account_id)))

        messages = (
            request.env["mail.message"].sudo().search(domain, order="date_received asc")
        )

        result = []
        for msg in messages:
            attachments = (
                request.env["ir.attachment"]
                .sudo()
                .search([("res_model", "=", "mail.message"), ("res_id", "=", msg.id)])
            )
            attachment_list = [
                {
                    "id": att.id,
                    "name": att.name,
                    "url": f"/web/content/{att.id}",
                    "download_url": f"/web/content/{att.id}?download=true",
                    "mimetype": att.mimetype,
                }
                for att in attachments
            ]
            result.append(
                {
                    "id": msg.id,
                    "subject": msg.subject or "No Subject",
                    "sender": msg.email_sender or "Unknown Sender",
                    "to": msg.email_receiver or "",
                    "receiver": msg.email_receiver or "",
                    "cc": msg.email_cc or "",
                    "date_received": (
                        msg.date_received.strftime("%Y-%m-%d %H:%M:%S")
                        if msg.date_received
                        else ""
                    ),
                    "body": msg.body,
                    "attachments": attachment_list,
                    "thread_id": msg.thread_id or "",
                    "message_id": msg.message_id or "",
                    "is_read": msg.is_read,
                    "is_starred_mail": msg.is_starred_mail,
                    "is_sent_mail": msg.is_sent_mail,
                    "avatar_url": msg.avatar_url,
                    "labels": (msg.gmail_labels or "").split(",") if msg.gmail_labels else [],
                }
            )

        return {"status": "ok", "messages": result}

    @http.route("/gmail/advanced_search", type="json", auth="user", csrf=False)
    def advanced_search(self, **kwargs):
        account_id = kwargs.get("account_id")
        page = int(kwargs.get("page", 1))
        limit = int(kwargs.get("limit", 15))
        offset = (page - 1) * limit

        account = request.env["gmail.account"].sudo().browse(int(account_id))
        if not account.exists():
            return {"messages": [], "total": 0}

        # Build Gmail API query string
        q = []
        if kwargs.get("from"):
            q.append(f'from:{kwargs["from"]}')
        if kwargs.get("to"):
            q.append(f'to:{kwargs["to"]}')
        if kwargs.get("subject"):
            q.append(f'subject:{kwargs["subject"]}')
        if kwargs.get("hasWords"):
            q.append(kwargs["hasWords"])
        if kwargs.get("doesntHave"):
            q.append(f'-{kwargs["doesntHave"]}')
        if kwargs.get("hasAttachment"):
            q.append("has:attachment")
        if kwargs.get("dateWithin"):
            if kwargs["dateWithin"] == "1 day":
                q.append("newer_than:1d")
            elif kwargs["dateWithin"] == "1 week":
                q.append("newer_than:7d")
            elif kwargs["dateWithin"] == "1 month":
                q.append("newer_than:30d")
        if kwargs.get("dateValue"):
            q.append(f'before:{kwargs["dateValue"].replace("-", "/")}')
        if kwargs.get("searchIn") and kwargs["searchIn"] != "all":
            if kwargs["searchIn"] == "inbox":
                q.append("in:inbox")
            elif kwargs["searchIn"] == "sent":
                q.append("in:sent")
            elif kwargs["searchIn"] == "drafts":
                q.append("in:drafts")
            elif kwargs["searchIn"] == "spam":
                q.append("in:spam")
        query_str = " ".join(q).strip()

        headers = {"Authorization": f"Bearer {account.access_token}"}
        params = {
            "q": query_str,
            "maxResults": limit,
        }
        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

        messages = []
        total = 0
        page_token = None
        page_num = 1
        while True:
            if page_token:
                params["pageToken"] = page_token
            else:
                params.pop("pageToken", None)
            _logger.info(
                f"🔎 [GMAIL SEARCH] Fetching page {page_num} with params: {params}"
            )
            resp = requests.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                _logger.error(
                    f"❌ [GMAIL SEARCH] Gmail API error page {page_num}: {resp.text}"
                )
                break

            data = resp.json()
            if page_num == 1:
                total = data.get("resultSizeEstimate", 0)
            message_ids = [m["id"] for m in data.get("messages", [])]
            _logger.info(
                f"🔎 [GMAIL SEARCH] Page {page_num} got {len(message_ids)} messages"
            )

            for gmail_id in message_ids:
                detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{gmail_id}?format=full"
                detail_resp = requests.get(detail_url, headers=headers)
                if detail_resp.status_code != 200:
                    _logger.warning(
                        f"⚠️ [GMAIL SEARCH] Failed to fetch detail for {gmail_id}"
                    )
                    continue
                msg_data = detail_resp.json()
                payload = msg_data.get("payload", {})

                def extract_header(payload, header_name):
                    for h in payload.get("headers", []):
                        if h.get("name", "").lower() == header_name.lower():
                            return h.get("value", "")
                    return ""

                subject = extract_header(payload, "Subject") or "No Subject"
                sender = extract_header(payload, "From")
                receiver = extract_header(payload, "To")
                cc = extract_header(payload, "Cc")
                date_received = extract_header(payload, "Date")
                thread_id = msg_data.get("threadId", "")
                message_id = extract_header(payload, "Message-Id")

                def extract_body(payload):
                    if payload.get("mimeType") == "text/html" and payload.get(
                        "body", {}
                    ).get("data"):
                        import base64

                        return base64.urlsafe_b64decode(
                            payload["body"]["data"] + "=="
                        ).decode("utf-8", errors="ignore")
                    for part in payload.get("parts", []):
                        body = extract_body(part)
                        if body:
                            return body
                    return ""

                body = extract_body(payload)
                messages.append(
                    {
                        "id": gmail_id,
                        "subject": subject,
                        "sender": sender,
                        "to": receiver,
                        "receiver": receiver,
                        "cc": cc,
                        "date_received": date_received,
                        "body": body,
                        "attachments": [],
                        "thread_id": thread_id,
                        "message_id": message_id,
                        "is_read": False,
                        "is_starred_mail": False,
                    }
                )

            page_token = data.get("nextPageToken")
            if not page_token:
                _logger.info(f"🔎 [GMAIL SEARCH] No more pages after page {page_num}")
                break
            page_num += 1
        return {"messages": messages, "total": total}
