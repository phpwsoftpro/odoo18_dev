from odoo import models, fields, api
from datetime import datetime


class OutlookMessage(models.Model):
    _name = "outlook.message"
    _description = "Cached Outlook Message"
    _rec_name = "subject"
    _order = "date desc, id desc"

    # ===== Khóa & liên kết
    user_id = fields.Many2one("res.users", required=True, index=True)
    account_id = fields.Many2one("outlook.account", index=True)  # NEW
    outlook_msg_id = fields.Char("Graph Message ID", required=True, index=True)
    internet_message_id = fields.Char(index=True)  # NEW (RFC822)
    thread_id = fields.Char("Conversation ID", index=True)
    folder = fields.Selection([("inbox", "Inbox"), ("sent", "Sent")], index=True)

    # ===== Thông tin chính
    subject = fields.Char()
    sender_name = fields.Char()
    sender_address = fields.Char()

    # Thời gian
    date = fields.Datetime(index=True)  # dùng để sort chung (giữ)
    sent_datetime = fields.Datetime(index=True)  # NEW
    received_datetime = fields.Datetime(index=True)  # NEW

    # Người nhận
    to_addresses = fields.Text()  # NEW ("Name <email>, Name <email>")
    cc_addresses = fields.Text()  # NEW
    bcc_addresses = fields.Text()  # NEW
    reply_to_addresses = fields.Text()  # NEW

    # Trạng thái & meta
    is_read = fields.Boolean(default=False, index=True)  # NEW
    has_attachments = fields.Boolean(default=False, index=True)  # NEW
    attachments_count = fields.Integer(default=0)  # NEW
    importance = fields.Selection(
        [("low", "Low"), ("normal", "Normal"), ("high", "High")],
        default="normal",
        index=True,
    )  # NEW
    categories = fields.Char()  # NEW (join list)
    body_preview = fields.Text()  # NEW

    # Nội dung
    body_html = fields.Html(sanitize=False)
    content_type = fields.Char()
    body_text = fields.Text()

    _sql_constraints = [
        ("uniq_outlook_msg_id", "unique(outlook_msg_id)", "Message already cached."),
    ]

    @staticmethod
    def _parse_graph_dt(s):
        """Parse ISO8601 from Microsoft Graph -> datetime (UTC)."""
        if not s:
            return None
        try:
            if isinstance(s, str) and s.endswith("Z"):
                s = s.replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except Exception:
            return None

    @api.model
    def upsert_from_graph_detail(
        self,
        detail: dict,
        folder_hint: str = "inbox",
        user_id: int = None,
        account_id: int = None,  # NEW (optional)
    ):
        if not detail or not detail.get("id"):
            return False

        # ---- helpers
        def _join_recipients(lst):
            """Convert list of {emailAddress:{name,address}} to 'Name <addr>' CSV."""
            out = []
            for r in lst or []:
                ea = (r or {}).get("emailAddress") or {}
                name = ea.get("name") or ""
                addr = ea.get("address") or ""
                if addr:
                    out.append(f"{name} <{addr}>" if name else addr)
            return ", ".join(out)

        is_sent = bool(detail.get("sentDateTime"))

        sent_dt = self._parse_graph_dt(detail.get("sentDateTime"))
        recv_dt = self._parse_graph_dt(detail.get("receivedDateTime"))
        # date tổng hợp: ưu tiên giờ gửi nếu có, ngược lại giờ nhận
        chosen_dt = sent_dt or recv_dt
        odoo_date = fields.Datetime.to_string(chosen_dt) if chosen_dt else False

        vals = {
            "user_id": user_id or self.env.user.id,
            "account_id": account_id,
            "outlook_msg_id": detail["id"],
            "internet_message_id": detail.get("internetMessageId"),
            "thread_id": detail.get("conversationId"),
            "folder": "sent" if is_sent or folder_hint == "sent" else "inbox",
            "subject": detail.get("subject"),
            "sender_name": (detail.get("sender") or {})
            .get("emailAddress", {})
            .get("name"),
            "sender_address": (detail.get("from") or {})
            .get("emailAddress", {})
            .get("address")
            or (detail.get("sender") or {}).get("emailAddress", {}).get("address"),
            "date": odoo_date,
            "sent_datetime": fields.Datetime.to_string(sent_dt) if sent_dt else False,
            "received_datetime": (
                fields.Datetime.to_string(recv_dt) if recv_dt else False
            ),
            "to_addresses": _join_recipients(detail.get("toRecipients")),
            "cc_addresses": _join_recipients(detail.get("ccRecipients")),
            "bcc_addresses": _join_recipients(detail.get("bccRecipients")),
            "reply_to_addresses": _join_recipients(detail.get("replyTo")),
            "is_read": bool(detail.get("isRead")),
            "has_attachments": bool(detail.get("hasAttachments")),
            "attachments_count": int(
                detail.get("attachmentsCount") or 0
            ),  # có nếu expand
            "importance": (detail.get("importance") or "normal").lower(),
            "categories": ", ".join(detail.get("categories") or []),
            "body_preview": detail.get("bodyPreview") or "",
            "body_html": (detail.get("body") or {}).get("content") or "",
            "content_type": (detail.get("body") or {}).get("contentType") or "html",
        }

        # Optional plain text
        body_html = vals["body_html"] or ""
        try:
            from lxml import html as lxml_html

            parsed = lxml_html.fromstring(body_html)
            vals["body_text"] = (parsed.text_content() or "").strip()
        except Exception:
            vals["body_text"] = ""

        rec = self.search([("outlook_msg_id", "=", detail["id"])], limit=1)
        if rec:
            rec.write(vals)
            return rec
        return self.create(vals)
