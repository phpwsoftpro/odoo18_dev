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
from datetime import timedelta

_logger = logging.getLogger(__name__)
def _split_addr(addr):
    return [a.strip() for a in re.split(r"[,\s;]+", addr or "") if a.strip()]


def _split_addr(addr):
    """split chuỗi địa chỉ bởi , ; hoặc khoảng trắng"""
    return [a.strip() for a in re.split(r"[,\s;]+", addr or "") if a.strip()]


class GmailInboxController(http.Controller):

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

    @http.route("/gmail/delete_message", type="json", auth="user", csrf=False)
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
            msg = request.env["mail.message"].sudo().browse(mid)
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
                    trash_url, headers={"Authorization": f"Bearer {token}"}
                )
            except Exception as e:
                _logger.error("HTTP request failed: %s", e)
                return {"success": False, "error": str(e)}

            if resp.status_code == 401:
                # Nếu 401, thử refresh lần nữa và retry
                acct.refresh_access_token()
                token = acct.access_token
                resp = requests.post(
                    trash_url, headers={"Authorization": f"Bearer {token}"}
                )

            if resp.status_code != 200:
                _logger.error("Gmail trash failed %s: %s", resp.status_code, resp.text)
                return {
                    "success": False,
                    "error": f"Gmail trash HTTP {resp.status_code}",
                }

            _logger.info("Moved Gmail ID %s to Trash (HTTP)", msg.gmail_id)

            # Xóa attachments & notification
            request.env["ir.attachment"].sudo().search(
                [
                    ("res_model", "=", "mail.message"),
                    ("res_id", "=", msg.id),
                ]
            ).unlink()
            request.env["mail.notification"].sudo().search(
                [
                    ("mail_message_id", "=", msg.id),
                ]
            ).unlink()

            # Xóa record Odoo
            msg.unlink()

        return {"success": True, "deleted_ids": ids}

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
        needs_refresh = (not token) or (acct.token_expiry and acct.token_expiry < now)

        if needs_refresh:
            _logger.info("🔄 Refreshing Gmail access token…")
            config = request.env["mail.message"].sudo().get_google_config()

            try:
                resp = requests.post(
                    config.get("token_uri") or "https://oauth2.googleapis.com/token",
                    data={
                        "client_id":     config["client_id"],
                        "client_secret": config["client_secret"],
                        "refresh_token": acct.refresh_token,
                        "grant_type":    "refresh_token",
                    },
                    timeout=15,
                )
            except requests.exceptions.RequestException as e:
                _logger.error("❌ Gmail token request failed: %s", e, exc_info=True)
                return request.make_json_response(
                    {"status": "error", "message": "Token request failed"}, status=502
                )

            raw_text = resp.text
            try:
                tok = resp.json()
            except ValueError:
                tok = {"error": raw_text[:200]}

            if resp.status_code != 200:
                _logger.error("❌ Gmail token refresh %s: %s", resp.status_code, raw_text)

                # 400/401: refresh_token hết hạn/bị revoke hoặc client_id/secret sai → yêu cầu re-auth
                if resp.status_code in (400, 401):
                    # hạ token để FE biết bật lại flow re-auth
                    acct.sudo().write({"access_token": False, "token_expiry": False})
                    return request.make_json_response({
                        "status": "error",
                        "code": resp.status_code,
                        "message": tok.get("error_description") or tok.get("error") or "Unauthorized token refresh",
                        "need_reauth": True,
                    }, status=200)

                # Lỗi khác: vẫn trả JSON để FE hiển thị
                return request.make_json_response({
                    "status": "error",
                    "code": resp.status_code,
                    "message": tok.get("error_description") or tok.get("error") or "Token refresh failed",
                }, status=200)

            token = tok.get("access_token")
            if not token:
                return request.make_json_response(
                    {"status": "error", "message": "No access_token in token response"},
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
        _logger.info("message_id FE gửi lên: %r", message_id)
        root["Subject"] = subject
        if message_id:
            # bảo đảm không bị <<...>> nếu FE đã kèm <>
            mid = message_id.strip()
            if not mid.startswith("<"):
                mid = f"<{mid}>"
            root["In-Reply-To"] = mid
            root["References"]  = mid

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
