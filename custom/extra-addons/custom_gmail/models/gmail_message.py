import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import re
from html import unescape
from lxml import html, etree
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class GmailMessage(models.Model):
    _inherit = "mail.message"

    sender_name = fields.Char(string="Sender Name")
    receiver_name = fields.Char(string="Receiver Name")
    avatar_url = fields.Char(string="Avatar URL")
    # gmail_labels = fields.Char(string="Gmail Labels")
    gmail_id = fields.Char(string="Gmail ID", index=True)
    gmail_body = fields.Text(string="Body")
    is_gmail = fields.Boolean(string="Is Gmail Message", default=False)
    is_sent_mail = fields.Boolean(string="Is Sent Mail", default=False)
    is_draft_mail = fields.Boolean(string="Is Draft Mail", default=False)
    is_starred_mail = fields.Boolean(string="Is Starred Mail", default=False)
    date_received = fields.Datetime(string="Date Received")
    email_sender = fields.Char(string="Email Sender")
    email_receiver = fields.Char(string="Email Receiver")
    email_cc = fields.Char(string="Email CC")
    last_fetched_email_id = fields.Char(string="Last Fetched Email ID")
    thread_id = fields.Char(string="Thread ID")
    message_id = fields.Char(string="Message ID")
    is_fetched_now = fields.Boolean(default=False)
    gpt_summary = fields.Text(string="GPT Summary")
    is_read = fields.Boolean(string="Is Read", default=False)

    gmail_account_id = fields.Many2one(
        "gmail.account", string="Gmail Account", index=True
    )

    _sql_constraints = [
        ("unique_gmail_id", "unique(gmail_id)", "Gmail ID must be unique!")
    ]

    def clean_html_content(self, html_content):
        """Clean HTML content and extract meaningful text"""
        if not html_content:
            return ""

        try:
            # Parse HTML and extract text
            tree = html.fromstring(html_content)

            # Remove script and style elements
            for element in tree.xpath("//script | //style"):
                element.getparent().remove(element)

            # Get text content
            text = tree.text_content()

            # Clean up whitespace and decode HTML entities
            text = unescape(text)
            text = re.sub(
                r"\s+", " ", text
            )  # Replace multiple spaces with single space
            text = text.strip()

            return text
        except Exception as e:
            _logger.warning("Failed to parse HTML content: %s", str(e))
            # Fallback: simple HTML tag removal
            text = re.sub(r"<[^>]+>", "", html_content)
            text = unescape(text)
            text = re.sub(r"\s+", " ", text)
            return text.strip()

    # _logger.info("ở ngoài action_analyze")
    def action_analyze(self, email, analysis_text):
        """Create or update a CRM lead from this message and post analysis."""
        self.ensure_one()
        _logger.info("1 action_analyze")

        if not self.email_sender:
            _logger.warning("No email sender found for message %s", self.message_id)
            return {"error": "No email sender found"}

        try:
            # Tạo nội dung phân tích mới dạng HTML
            analysis_text_markup = (
                f"Nội dung từ Email:\n{email}\n\n📌AI Phân Tích:\n{analysis_text}"
            )

            # Tìm hoặc tạo đối tượng partner
            partner = self.env["res.partner"].search(
                [("email", "=", self.email_sender)], limit=1
            )
            if not partner:
                partner = self.env["res.partner"].create(
                    {"name": self.email_sender, "email": self.email_sender}
                )

            # Tìm CRM Lead đã tồn tại
            lead = self.env["crm.lead"].search(
                [("partner_id", "=", partner.id), ("email_from", "=", partner.email)],
                limit=1,
            )
            _logger.info("2 action_analyze")

            if lead:
                # Nếu có lead, ghi body_analyze cũ vào comment trước khi cập nhật
                old_body = lead.body_analyze
                if old_body:
                    lead.message_post(
                        body=old_body,
                        message_type="comment",
                        subtype_xmlid="mail.mt_note",
                    )
                # Cập nhật lại nội dung phân tích mới
                lead.body_analyze = analysis_text_markup
            else:

                # Nếu chưa có lead → tạo mới
                lead = self.env["crm.lead"].create(
                    {
                        "name": self.subject or "Gmail Lead - No Subject",
                        "email_from": partner.email,
                        "partner_id": partner.id,
                        "body_analyze": analysis_text_markup,
                    }
                )
                _logger.info("3 action_analyze")

            return {"lead_id": lead.id, "partner_id": partner.id}

        except Exception as e:
            _logger.error(
                "❌ Failed to create/update lead for message %s: %s",
                self.message_id,
                str(e),
            )
            return {"error": str(e)}

    def auto_analyze_gpt(self):
        self.ensure_one()

        if self.gpt_summary:
            _logger.info("⏩ GPT already analyzed, skipping: %s", self.message_id)
            return

        email_body = self.clean_html_content(self.body or "")
        max_chars = 8000
        if len(email_body) > max_chars:
            email_body = email_body[:max_chars] + "\n\n[...content truncated...]"

        prompt = f"""
        Please analyze this email and provide a concise summary in English:

        Subject: {self.subject or 'No Subject'}
        From: {self.email_sender or 'Unknown'}
        To: {self.email_receiver or 'Unknown'}

        Email Content:
        ---
        {email_body}
        ---

        Please provide a brief analysis covering:
        1. What does the sender want?
        2. Are they interested in working with us?
        3. Do they want us to send a CV/resume?
        4. Are they rejecting us?
        5. If they want to hire someone, provide a brief job description. Otherwise, state "No hiring request."

        Keep the response concise and professional.
        """

        try:
            _logger.info("🤖 Calling Flask GPT API for message_id: %s", self.message_id)

            login_payload = {"email": "lebadung@wsoftpro.com", "password": "zLrA3pN7"}
            login_resp = requests.post(
                "http://192.168.1.51:9999/login", json=login_payload, timeout=10
            )
            token = login_resp.json().get("token")
            if not token:
                raise Exception("No token returned from Flask GPT API")

            payload = {
                "text": prompt,
                "email": self.email_sender or "unknown@example.com",
                "image_base64": None,
            }
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.post(
                "http://192.168.1.51:9999/api/status",
                json=payload,
                headers=headers,
                timeout=None,
            )

            if resp.status_code != 200:
                raise Exception(f"GPT API error {resp.status_code}: {resp.text}")

            ai_summary = resp.json().get("result", "GPT returned no result")

            self.write({"gpt_summary": ai_summary, "is_fetched_now": False})

            # Tạo CRM Lead như trước
            result = self.action_analyze(email_body, ai_summary)

            _logger.info("✅ GPT analysis completed for: %s", self.message_id)
            return result

        except Exception as e:
            error_msg = f"GPT analysis failed for message {self.message_id}: {str(e)}"
            _logger.exception("❌ %s", error_msg)

            self.write(
                {"gpt_summary": f"Analysis failed: {str(e)}", "is_fetched_now": False}
            )
            return {"error": error_msg}

    @api.model
    def batch_analyze_pending_messages(self, limit=10):
        """Batch process pending messages for GPT analysis"""
        pending_messages = self.search(
            [
                ("is_gmail", "=", True),
                ("gpt_summary", "=", False),
                ("is_fetched_now", "=", True),
            ],
            limit=limit,
            order="create_date desc",
        )

        if not pending_messages:
            _logger.info("No pending messages for GPT analysis")
            return

        _logger.info(
            "🤖 Processing %s pending messages for GPT analysis", len(pending_messages)
        )

        success_count = 0
        error_count = 0

        for message in pending_messages:
            try:
                result = message.auto_analyze_gpt()
                if result and not result.get("error"):
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                _logger.error(
                    "Failed to analyze message %s: %s", message.message_id, str(e)
                )
                error_count += 1

        _logger.info(
            "✅ Batch analysis completed: %s success, %s errors",
            success_count,
            error_count,
        )
        return {"success": success_count, "errors": error_count}
