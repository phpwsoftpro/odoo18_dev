from odoo import models, fields, api
from datetime import datetime


class OutlookMessage(models.Model):
    _name = "outlook.message"
    _description = "Cached Outlook Message"
    _rec_name = "subject"
    _order = "date desc, id desc"

    user_id = fields.Many2one("res.users", required=True, index=True)
    outlook_msg_id = fields.Char("Graph Message ID", required=True, index=True)
    thread_id = fields.Char("Conversation ID", index=True)
    folder = fields.Selection([("inbox", "Inbox"), ("sent", "Sent")], index=True)

    subject = fields.Char()
    sender_name = fields.Char()
    sender_address = fields.Char()
    date = fields.Datetime(index=True)

    body_html = fields.Html(sanitize=False)
    content_type = fields.Char()
    body_text = fields.Text()

    _sql_constraints = [
        ("uniq_outlook_msg_id", "unique(outlook_msg_id)", "Message already cached.")
    ]

    @staticmethod  # ✅ thêm staticmethod
    def _parse_graph_dt(s):
        """Parse ISO8601 từ Microsoft Graph -> datetime (UTC)."""
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
        self, detail: dict, folder_hint: str = "inbox", user_id: int = None
    ):
        if not detail or not detail.get("id"):
            return False

        is_sent = bool(detail.get("sentDateTime"))
        dt_raw = (
            detail.get("sentDateTime") if is_sent else detail.get("receivedDateTime")
        )
        dt_obj = self._parse_graph_dt(dt_raw)  # ✅ gọi qua self (hoặc type(self))
        odoo_dt = fields.Datetime.to_string(dt_obj) if dt_obj else False

        vals = {
            "user_id": user_id or self.env.user.id,
            "outlook_msg_id": detail["id"],
            "thread_id": detail.get("conversationId"),
            "folder": "sent" if is_sent or folder_hint == "sent" else "inbox",
            "subject": detail.get("subject"),
            "sender_name": (detail.get("sender") or {})
            .get("emailAddress", {})
            .get("name"),
            "sender_address": (detail.get("sender") or {})
            .get("emailAddress", {})
            .get("address"),
            "date": odoo_dt,
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

        record = self.search([("outlook_msg_id", "=", detail["id"])], limit=1)
        if record:
            record.write(vals)
            return record
        return self.create(vals)
