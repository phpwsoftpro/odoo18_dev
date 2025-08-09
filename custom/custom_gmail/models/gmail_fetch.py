import json
import requests
import logging
from odoo import models, api, fields
import base64
from lxml import html
import mimetypes
import pytz
from datetime import datetime, timedelta
from dateutil import parser
from email.utils import parsedate_to_datetime

import re
from odoo.http import request


_logger = logging.getLogger(__name__)


def replace_cid_links(html_body, attachments):
    try:
        tree = html.fromstring(html_body)
        for img in tree.xpath("//img"):
            src = img.get("src", "")
            if src.startswith("cid:"):
                cid_name = src.replace("cid:", "").strip("<>")
                for att in attachments:
                    possible_cids = [
                        (att.description or "").strip("<>"),
                        (att.description or "").split("@")[0],
                        att.name or "",
                    ]
                    if cid_name in possible_cids:
                        img.set("src", f"/web/content/{att.id}")
                        _logger.debug(
                            "🔁 Replaced CID %s → /web/content/%s", cid_name, att.id
                        )
                        break
        return html.tostring(tree, encoding="unicode")
    except Exception as e:
        _logger.warning("⚠️ CID replacement failed: %s", e)
        return html_body


class GmailFetch(models.Model):
    _inherit = "mail.message"

    @api.model
    def action_redirect_gmail_auth(self):
        config_params = self.env["ir.config_parameter"].sudo()
        config_params.set_param("gmail_access_token", "")
        config_params.set_param("gmail_refresh_token", "")
        config_params.set_param("gmail_authenticated_email", "")

        access_token = config_params.get_param("gmail_access_token")
        if access_token:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "X-API-KEY": "my-secret-key",
            }
            profile_response = requests.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers=headers,
            )
            if profile_response.status_code == 200:
                email_address = profile_response.json().get("emailAddress")
                config_params.set_param("gmail_authenticated_email", email_address)
                _logger.info("Authenticated Gmail address: %s", email_address)

                try:
                    self.fetch_gmail_messages(access_token)
                    return {"type": "ir.actions.client", "tag": "reload"}
                except Exception as e:
                    _logger.warning("Access token có thể thiếu quyền: %s", str(e))

            _logger.warning("Access token is invalid or lacks permission.")

        config = self.get_google_config()
        scope = (
            "https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/gmail.send "
            "https://www.googleapis.com/auth/gmail.compose "
            "https://www.googleapis.com/auth/gmail.modify"
        )
        auth_url = (
            f"{config['auth_uri']}?response_type=code"
            f"&client_id={config['client_id']}"
            f"&redirect_uri={config['redirect_uri']}"
            f"&scope={scope.replace(' ', '%20')}"
            f"&access_type=offline"
            f"&prompt=consent%20select_account"
            f"&include_granted_scopes=false"
        )

        _logger.info("Redirect URL generated: %s", auth_url)

        return {
            "type": "ir.actions.act_url",
            "url": str(auth_url),
            "target": "new",
        }

    def save_attachments(self, payload, gmail_msg_id, res_id, headers):
        saved_attachments = []

        def recurse(part):
            filename = part.get("filename")
            body_info = part.get("body", {})
            att_id = body_info.get("attachmentId")
            content_id = part.get("headers", [])

            cid = next(
                (
                    h.get("value").strip("<>")
                    for h in content_id
                    if h.get("name") == "Content-ID"
                ),
                None,
            )

            if filename and att_id:
                att_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{gmail_msg_id}/attachments/{att_id}"
                att_response = requests.get(att_url, headers=headers)
                if att_response.status_code == 200:
                    att_data = att_response.json().get("data")
                    if att_data:
                        try:
                            file_data = base64.urlsafe_b64decode(att_data + "==")
                        except Exception as e:
                            _logger.warning(
                                "❌ Lỗi decode attachment %s: %s", filename, e
                            )
                            return

                        mimetype = (
                            part.get("mimeType")
                            or mimetypes.guess_type(filename)[0]
                            or "application/octet-stream"
                        )

                        att_vals = {
                            "name": filename,
                            "datas": base64.b64encode(file_data).decode("utf-8"),
                            "res_model": "mail.message",
                            "res_id": res_id,
                            "mimetype": mimetype,
                            "type": "binary",
                        }

                        if cid:
                            att_vals["description"] = cid

                        att = self.env["ir.attachment"].sudo().create(att_vals)
                        saved_attachments.append(att)
                        _logger.debug(
                            "✅ Attachment saved: %s - CID: %s - Type: %s",
                            filename,
                            cid,
                            mimetype,
                        )

            for sub in part.get("parts", []):
                recurse(sub)

        recurse(payload)
        return saved_attachments

    def wrap_html(self, html_body):
        if "<html" not in html_body.lower():
            return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8" /></head>
<body>{html_body}</body>
</html>"""
        return html_body

    def extract_all_html_parts(self, payload):
        html_parts = []

        def recurse(part):
            mime_type = part.get("mimeType")
            body_data = part.get("body", {}).get("data")
            if mime_type == "text/html" and body_data:
                try:
                    html_parts.append(
                        base64.urlsafe_b64decode(body_data + "==").decode("utf-8")
                    )
                except Exception as e:
                    _logger.warning("❌ Decode HTML failed: %s", e)
            for sub in part.get("parts", []):
                recurse(sub)

        recurse(payload)
        return "\n".join(html_parts) if html_parts else ""

    def fetch_gmail_for_account(
        self,
        account,
        # query="in:inbox",
        query=None,
        is_sent=False,
        skip_recent_check=False,
        is_draft=False,
        is_starred=False,  # ✅ thêm tham số này
    ):
        if account.token_expiry and account.token_expiry < datetime.utcnow():
            _logger.info(f"🔄 Token expired for {account.email}, refreshing...")
            success = self.env["gmail.account"].sudo().refresh_access_token(account)
            if not success:
                raise ValueError(f"❌ Failed to refresh token for {account.email}")

        headers = {"Authorization": f"Bearer {account.access_token}"}
        max_messages = 30
        fetched_count = 0
        next_page_token = None
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        if is_draft:
            base_url = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"

        sync_state = (
            self.env["gmail.account.sync.state"]
            .sudo()
            .search([("gmail_account_id", "=", account.id)], limit=1)
        )

        if not sync_state:
            sync_state = (
                self.env["gmail.account.sync.state"]
                .sudo()
                .create({"gmail_account_id": account.id})
            )

        # ⏱️ Skip fetch nếu mới fetch dưới 30s
        if not skip_recent_check:
            if (
                sync_state.last_fetch_at
                and (datetime.utcnow() - sync_state.last_fetch_at).total_seconds() < 30
            ):
                _logger.info("⏳ Bỏ qua fetch: đã đồng bộ gần đây.")
                return True

        existing_msgs = self.search(
            [
                ("gmail_id", "!=", False),
                ("gmail_account_id", "=", account.id),
                ("create_date", ">", datetime.utcnow() - timedelta(days=30)),
            ]
        )
        existing_gmail_map = {msg.gmail_id: msg for msg in existing_msgs}
        existing_gmail_ids = set(existing_gmail_map.keys())

        while fetched_count < max_messages:
            params = {"maxResults": 15}
            if not is_draft:
                params["q"] = query
            if next_page_token:
                params["pageToken"] = next_page_token

            response = requests.get(base_url, headers=headers, params=params)
            _logger.debug("📨 Gmail API RAW response: %s", response.text)

            if response.status_code != 200:
                _logger.error("❌ Failed to fetch message list: %s", response.text)
                return

            if is_draft:
                draft_objs = response.json().get("drafts", [])
                messages = [{"id": d.get("id")} for d in draft_objs]
                next_page_token = response.json().get("nextPageToken")
            else:
                messages = response.json().get("messages", [])
                next_page_token = response.json().get("nextPageToken")

            if not messages:
                break

            for msg in messages:
                if fetched_count >= max_messages:
                    break

                gmail_id = msg.get("id")
                existing_msg = existing_gmail_map.get(gmail_id)
                if not existing_msg:
                    existing_msg = self.search([("gmail_id", "=", gmail_id)], limit=1)
                    if existing_msg:
                        existing_gmail_map[gmail_id] = existing_msg
                        existing_gmail_ids.add(gmail_id)

                if existing_msg:
                    if is_sent and not existing_msg.is_sent_mail:
                        existing_msg.sudo().write({"is_sent_mail": True})
                        _logger.debug(
                            "✏️ Đánh dấu is_sent_mail cho message %s", gmail_id
                        )
                    else:
                        _logger.debug("🔁 Đã tồn tại trong DB, bỏ qua: %s", gmail_id)
                    continue

                detail_url = f"{base_url}/{gmail_id}?format=full"
                message_response = requests.get(detail_url, headers=headers)
                if message_response.status_code != 200:
                    _logger.warning("❌ Lỗi khi lấy chi tiết message %s", gmail_id)
                    continue

                msg_data = message_response.json()
                if is_draft:
                    msg_data = msg_data.get("message", {})

                payload = msg_data.get("payload", {})

                def extract_header(payload, header_name):
                    headers = payload.get("headers", [])
                    for h in headers:
                        if h.get("name", "").lower() == header_name.lower():
                            return h.get("value", "")
                    for part in payload.get("parts", []):
                        result = extract_header(part, header_name)
                        if result:
                            return result
                    return ""

                subject = extract_header(payload, "Subject") or "No Subject"
                sender = extract_header(payload, "From")
                receiver = extract_header(payload, "To")
                cc = extract_header(payload, "Cc")
                raw_date = extract_header(payload, "Date")
                try:
                    dt = parser.parse(raw_date)
                    user_tz = pytz.timezone(account.user_id.tz or "UTC")
                    dt = dt.astimezone(user_tz)
                    date_received = dt.replace(tzinfo=None)
                except Exception as e:
                    _logger.warning("⚠️ Parse date thất bại: %s (%s)", raw_date, e)
                    date_received = None
                raw_message_id = extract_header(payload, "Message-Id")
                message_id = raw_message_id.strip("<>") if raw_message_id else ""
                label_ids = msg_data.get("labelIds", [])
                # body_html = self.env["mail.message"].extract_all_html_parts(payload)
                raw_html = self.extract_all_html_parts(payload)
                body_html_wrapped = self.wrap_html(raw_html)
                body_html = body_html_wrapped
                # 2. Làm sạch: loại <br>, comment, rồi tách plain text
                try:
                    cleaned_html = (
                        body_html_wrapped.replace("<br>", "\n")
                        .replace("<br/>", "\n")
                        .replace("<br/>", "\n")
                    )
                    cleaned_html = re.sub(
                        r"<!--.*?-->", "", cleaned_html, flags=re.DOTALL
                    )
                    parsed_html = html.fromstring(cleaned_html)
                    cleaned_body = parsed_html.text_content().strip()
                except Exception as e:
                    _logger.warning("⚠️ Không thể làm sạch body HTML: %s", e)
                    cleaned_body = raw_html

                # 3. Gán tạm updated_html = cleaned_html
                updated_html = cleaned_html

                # 4. Tạo message với plain text là body_plain, HTML là body

                try:
                    message = (
                        self.env["mail.message"]
                        .sudo()
                        .create(
                            {
                                "gmail_id": gmail_id,
                                "gmail_account_id": account.id,
                                "is_gmail": True,
                                "is_sent_mail": is_sent,
                                "is_draft_mail": is_draft,
                                "body": body_html,
                                "subject": subject,
                                "date_received": date_received,
                                "message_type": "email",
                                "author_id": account.user_id.partner_id.id,
                                "email_sender": sender,
                                "email_receiver": receiver,
                                "email_cc": cc,
                                "thread_id": msg.get("threadId"),
                                "message_id": message_id,
                                # "gmail_labels": ",".join(label_ids),
                            }
                        )
                    )

                    _logger.info(
                        "🧱 Message created: ID=%s, Subject=%s",
                        message.id,
                        message.subject,
                    )

                except Exception as e:
                    error_msg = str(e)
                    if (
                        "duplicate key value violates unique constraint" in error_msg
                        and "gmail_id" in error_msg
                    ):
                        _logger.warning(
                            "⚠️ Gmail message trùng gmail_id=%s → bỏ qua.", gmail_id
                        )
                        continue  # skip to next message
                    else:
                        _logger.exception(
                            "❌ Lỗi không xác định khi tạo message gmail_id=%s: %s",
                            gmail_id,
                            error_msg,
                        )
                        continue

                _logger.info(
                    "🧱 Message created: ID=%s, Subject=%s", message.id, message.subject
                )

                attachments = self.env["mail.message"].save_attachments(
                    payload, gmail_id, message.id, headers
                )
                if attachments and "cid:" in body_html:
                    updated_body = replace_cid_links(body_html, attachments)
                    message.body = updated_body

                message.is_fetched_now = True

                fetched_count += 1

            if not next_page_token or fetched_count >= max_messages:
                break

        try:
            synced_ids = existing_gmail_ids.union(
                set(
                    self.env["mail.message"]
                    .search(
                        [
                            ("is_gmail", "=", True),
                            ("author_id", "=", account.user_id.partner_id.id),
                            ("create_date", ">=", datetime.now() - timedelta(days=30)),
                        ]
                    )
                    .mapped("gmail_id")
                )
            )

            sync_state.write(
                {
                    "last_fetch_at": fields.Datetime.now(),
                    "gmail_ids_30_days": json.dumps(list(synced_ids)),
                }
            )
        except Exception as e:
            _logger.warning("⚠️ Không thể cập nhật sync state: %s", e)

        try:
            # Chỉ cập nhật has_new_mail cho inbox thông thường
            if not is_sent and not is_draft and not is_starred:
                account.sudo().write({"has_new_mail": fetched_count > 0})
        except Exception as e:
            _logger.warning("⚠️ Không thể cập nhật cờ has_new_mail: %s", e)

        _logger.info("✅ Đồng bộ Gmail hoàn tất (%s messages)", fetched_count)
        return True

    @api.model
    def fetch_gmail_sent_for_account(self, account):
        """Fetch sent emails for the given Gmail account"""
        return self.fetch_gmail_for_account(
            account,
            query="in:sent",
            is_sent=True,
            skip_recent_check=True,
        )

    @api.model
    def fetch_gmail_drafts_for_account(self, account):
        """Fetch draft emails for the given Gmail account"""
        return self.fetch_gmail_for_account(
            account,
            query="in:drafts",
            is_sent=False,
            skip_recent_check=True,
            is_draft=True,
        )

    @api.model
    def fetch_gmail_starred_for_account(self, account):
        """Fetch starred emails for the given Gmail account"""
        return self.fetch_gmail_for_account(
            account,
            query="in:starred",
            is_sent=False,
            skip_recent_check=True,
            is_draft=False,
            is_starred=True,  # ✅ thêm tham số này
        )
