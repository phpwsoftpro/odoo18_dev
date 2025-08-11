from odoo import models, fields, api

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

    # Store raw HTML to render 1:1 in frontend
    body_html = fields.Html(sanitize=False)
    content_type = fields.Char()
    # Optional: plain text for search/preview
    body_text = fields.Text()

    _sql_constraints = [
        ("uniq_outlook_msg_id", "unique(outlook_msg_id)", "Message already cached.")
    ]

    @api.model
    def upsert_from_graph_detail(self, detail: dict, folder_hint: str = "inbox", user_id: int = None):
        """Create or update a cached message from a Graph API message detail payload."""
        if not detail or not detail.get("id"):
            return False

        # Build values
        is_sent = bool(detail.get("sentDateTime"))
        vals = {
            "user_id": user_id or self.env.user.id,
            "outlook_msg_id": detail["id"],
            "thread_id": detail.get("conversationId"),
            "folder": "sent" if is_sent or folder_hint == "sent" else "inbox",
            "subject": detail.get("subject"),
            "sender_name": (detail.get("sender") or {}).get("emailAddress", {}).get("name"),
            "sender_address": (detail.get("sender") or {}).get("emailAddress", {}).get("address"),
            "date": detail.get("sentDateTime") if is_sent else detail.get("receivedDateTime"),
            "body_html": (detail.get("body") or {}).get("content") or "",
            "content_type": (detail.get("body") or {}).get("contentType") or "html",
        }

        # Optional plain text using lxml if available
        body_html = vals["body_html"] or ""
        try:
            from lxml import html as lxml_html
            parsed = lxml_html.fromstring(body_html)
            vals["body_text"] = (parsed.text_content() or "").strip()
        except Exception:
            vals["body_text"] = ""

        # Upsert by outlook_msg_id
        record = self.search([("outlook_msg_id", "=", detail["id"])], limit=1)
        if record:
            record.write(vals)
            return record
        return self.create(vals)
