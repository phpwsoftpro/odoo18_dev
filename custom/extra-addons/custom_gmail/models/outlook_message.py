# /mnt/extra-addons/custom_gmail/models/outlook_message.py
# -*- coding: utf-8 -*-
import base64
import logging
import requests

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class OutlookMessage(models.Model):
    _name = "outlook.message"
    _description = "Cached Outlook Message"
    _rec_name = "subject"
    _order = "date desc, id desc"

    # ===== Khóa & liên kết
    user_id = fields.Many2one("res.users", required=True, index=True)
    account_id = fields.Many2one("outlook.account", index=True)
    outlook_msg_id = fields.Char("Graph Message ID", required=True, index=True)
    internet_message_id = fields.Char(index=True)  # RFC822
    thread_id = fields.Char("Conversation ID", index=True)
    folder = fields.Selection([("inbox", "Inbox"), ("sent", "Sent")], index=True)

    # ===== Thông tin chính
    subject = fields.Char()
    sender_name = fields.Char()
    sender_address = fields.Char()

    # Thời gian
    date = fields.Datetime(index=True)
    sent_datetime = fields.Datetime(index=True)
    received_datetime = fields.Datetime(index=True)

    # Người nhận
    to_addresses = fields.Text()
    cc_addresses = fields.Text()
    bcc_addresses = fields.Text()
    reply_to_addresses = fields.Text()

    # Trạng thái & meta
    is_read = fields.Boolean(default=False, index=True)
    has_attachments = fields.Boolean(default=False, index=True)
    attachments_count = fields.Integer(default=0)
    importance = fields.Selection(
        [("low", "Low"), ("normal", "Normal"), ("high", "High")],
        default="normal",
        index=True,
    )
    categories = fields.Char()
    body_preview = fields.Text()

    # Nội dung
    body_html = fields.Html(sanitize=False)
    content_type = fields.Char()
    body_text = fields.Text()

    _sql_constraints = [
        ("uniq_outlook_msg_id", "unique(outlook_msg_id)", "Message already cached."),
    ]

    # (giữ nguyên method _parse_graph_dt và upsert_from_graph_detail của bạn)
    # ...

    def fetch_and_save_graph_attachments(self, account):
        """
        Gọi Graph để tải attachments cho chính message này (self),
        rồi lưu vào ir.attachment (res_model='outlook.message', res_id=self.id).
        """
        self.ensure_one()
        if not self.outlook_msg_id:
            return

        access_token = account.outlook_access_token or ""
        if not access_token:
            _logger.warning(
                "No access token to fetch attachments for %s", self.outlook_msg_id
            )
            return

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Gọi /attachments của 1 message
        url = f"https://graph.microsoft.com/v1.0/me/messages/{self.outlook_msg_id}/attachments"
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            _logger.error(
                "Fetch attachments failed %s: %s", self.outlook_msg_id, r.text
            )
            return

        items = r.json().get("value", [])
        IrAtt = self.env["ir.attachment"].sudo()
        saved = 0

        for it in items:
            odata_type = it.get("@odata.type", "")
            # Chỉ lưu fileAttachment; itemAttachment (email lồng, lịch) bỏ qua để đơn giản
            if "fileAttachment" not in odata_type:
                continue

            name = it.get("name") or "attachment"
            content_type = it.get("contentType") or "application/octet-stream"
            content_bytes = it.get("contentBytes")  # base64 string
            if not content_bytes:
                # Nếu API không trả contentBytes, có thể cần gọi detail /attachments/{id}
                att_id = it.get("id")
                if att_id:
                    det = requests.get(
                        f"https://graph.microsoft.com/v1.0/me/messages/{self.outlook_msg_id}/attachments/{att_id}",
                        headers=headers,
                    )
                    if det.status_code == 200:
                        content_bytes = det.json().get("contentBytes")

            if not content_bytes:
                continue

            # Tránh tạo trùng: tìm theo (res_model, res_id, name, datas_fname)
            exists = IrAtt.search(
                [
                    ("res_model", "=", "outlook.message"),
                    ("res_id", "=", self.id),
                    ("name", "=", name),
                ],
                limit=1,
            )
            if exists:
                continue

            IrAtt.create(
                {
                    "name": name,
                    "res_model": "outlook.message",
                    "res_id": self.id,
                    "type": "binary",
                    "datas": content_bytes,  # Graph đã trả base64 → dùng trực tiếp
                    "res_name": self.subject or name,
                    "mimetype": content_type,
                }
            )
            saved += 1

        # cập nhật đếm nếu cần
        if saved:
            self.write(
                {
                    "attachments_count": (self.attachments_count or 0) + saved,
                    "has_attachments": True,
                }
            )

    @api.model
    def _parse_graph_dt(self, s):
        if not s:
            return False
        try:
            return isoparse(s)
        except Exception:
            return False

    @api.model
    def _join_people(self, lst):
        items = []
        for it in lst or []:
            ea = (it or {}).get("emailAddress") or {}
            nm, ad = ea.get("name") or "", ea.get("address") or ""
            if ad:
                items.append(f"{nm} <{ad}>" if nm else ad)
        return ", ".join(items)

    @api.model
    def upsert_from_graph_detail(
        self,
        d,
        *,
        folder_hint="inbox",
        user_id=False,
        account_id=False,
        account_email=None,
    ):
        if not d or not d.get("id"):
            return False

        sent_dt = self._parse_graph_dt(d.get("sentDateTime"))
        recv_dt = self._parse_graph_dt(d.get("receivedDateTime"))
        date_any = recv_dt or sent_dt

        from_addr = ((d.get("from") or {}).get("emailAddress") or {}).get(
            "address"
        ) or ""
        me = (account_email or "").strip().lower()
        is_me_sender = from_addr.strip().lower() == me

        vals = {
            "user_id": user_id,
            "account_id": account_id,
            "outlook_msg_id": d["id"],
            "internet_message_id": d.get("internetMessageId") or False,
            "thread_id": d.get("conversationId")
            or d.get("internetMessageId")
            or d.get("id"),
            "subject": d.get("subject") or "",
            "sender_name": ((d.get("from") or {}).get("emailAddress") or {}).get("name")
            or ((d.get("sender") or {}).get("emailAddress") or {}).get("name")
            or "",
            "sender_address": from_addr,
            "to_addresses": self._join_people(d.get("toRecipients")),
            "cc_addresses": self._join_people(d.get("ccRecipients")),
            "bcc_addresses": self._join_people(d.get("bccRecipients")),
            "reply_to_addresses": self._join_people(
                d.get("replyTo") or d.get("replyToRecipients")
            ),
            "date": date_any,
            "sent_datetime": sent_dt,
            "received_datetime": recv_dt,
            "is_read": bool(d.get("isRead")),
            "has_attachments": bool(d.get("hasAttachments")),
            "body_preview": d.get("bodyPreview") or "",
            "body_html": ((d.get("body") or {}).get("content")) or "",
            "content_type": ((d.get("body") or {}).get("contentType")) or "html",
            # ✅ chỉ dùng folder_hint hoặc email người gửi để xác định Sent/Inbox
            "folder": "sent" if (folder_hint == "sent" or is_me_sender) else "inbox",
        }

        rec = self.sudo().search([("outlook_msg_id", "=", d["id"])], limit=1)
        return rec.write(vals) or rec if rec else self.sudo().create(vals)
