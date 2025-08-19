# /mnt/extra-addons/.../controllers/gmail_inbox_controller.py
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
from datetime import timedelta

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
                    "to": extract_email_only(msg.email_receiver or ""),
                    "receiver": msg.email_receiver or "Unknown Receiver",
                    "date_received": (
                        msg.date_received.strftime("%Y-%m-%d %H:%M:%S")
                        if msg.date_received
                        else ""
                    ),
                    "body": msg.body,
                    "cc": msg.email_cc or "",
                    "bcc": msg.email_bcc or "",
                    "attachments": attachment_list,
                    "thread_id": msg.thread_id or "",
                    "message_id": msg.message_id or "",
                    "is_read": msg.is_read,
                    "is_starred_mail": msg.is_starred_mail,
                    "avatar_url": msg.avatar_url,
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
                    "to": extract_email_only(msg.email_receiver or ""),
                    "receiver": msg.email_receiver or "Unknown Receiver",
                    "cc": msg.email_cc or "",
                    "bcc": msg.email_bcc or "",
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
                    "to": extract_email_only(msg.email_receiver or ""),
                    "receiver": msg.email_receiver or "Unknown Receiver",
                    "cc": msg.email_cc or "",  # <— thêm
                    "bcc": msg.email_bcc or "",
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
                    "to": extract_email_only(msg.email_receiver or ""),
                    "receiver": msg.email_receiver or "Unknown Receiver",
                    "cc": msg.email_cc or "",
                    "bcc": msg.email_bcc or "",
                    "date_received": (
                        msg.date_received.strftime("%Y-%m-%d %H:%M:%S")
                        if msg.date_received
                        else ""
                    ),
                    "body": full_body,
                    "attachments": attachment_list,
                    "thread_id": msg.thread_id or "",
                    "message_id": msg.message_id or "",
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
                    "to": extract_email_only(msg.email_receiver or ""),
                    "receiver": msg.email_receiver or "Unknown Receiver",
                    "cc": msg.email_cc or "",
                    "bcc": msg.email_bcc or "",
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
                    "bcc": msg.email_bcc or "",
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
                }
            )

        return {"status": "ok", "messages": result}
