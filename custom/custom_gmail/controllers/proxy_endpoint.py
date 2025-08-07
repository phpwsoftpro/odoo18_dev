# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import requests
import logging
from markupsafe import Markup

_logger = logging.getLogger(__name__)

class EmailAnalyzeController(http.Controller):

    @http.route('/analyze_email_proxy', type='json', auth='public', methods=['POST'], csrf=False)
    def analyze_email_proxy(self):
        if request.httprequest.headers.get('X-API-KEY') != 'my-secret-key':
            return {'error': 'Invalid API key'}

        try:
            data = request.params

            email_text = data.get('text', '').strip()
            subject = data.get('subject', 'No Subject')
            sender_name = data.get('sender_name', 'Người gửi không xác định')
            email_from = data.get('email_from', 'unknown@example.com').strip()
            html_body = data.get('html_body', email_text)
            message_id = data.get('message_id', '').strip()

            if not email_text:
                return {'error': 'No email body provided'}

            # ✅ Không xử lý nếu không có email thật
            if not email_from or email_from.lower() == "unknown@example.com":
                _logger.warning("❌ Không xác định được email người gửi — Bỏ qua.")
                return {'error': "❌ Không thể xác định địa chỉ email người gửi — không thể tạo partner."}

            # Step 1: 🔐 Đăng nhập lấy token từ Flask
            login_payload = {
                "email": "lebadung@wsoftpro.com",
                "password": "zLrA3pN7"
            }
            _logger.info("🔐 Đang đăng nhập để lấy token...")
            login_resp = requests.post("http://192.168.1.51:9999/login", json=login_payload, timeout=20)
            if login_resp.status_code != 200:
                _logger.error("❌ Đăng nhập Flask thất bại")
                return {'error': 'Login to analysis service failed'}

            token = login_resp.json().get("token")
            if not token:
                _logger.error("❌ Không nhận được token từ Flask")
                return {'error': 'No token returned from login'}

            # Step 2: Gửi nội dung email để AI phân tích
            # Bổ sung prompt rõ ràng
            prompt = f"""
            Please analyze this email and provide a concise summary in English:

            Subject: {subject}
            From: {email_from}
            To: unknown

            Email Content:
            ---
            {email_text}
            ---

            Please provide a brief analysis covering:
            1. What does the sender want?
            2. Are they interested in working with us?
            3. Do they want us to send a CV/resume?
            4. Are they rejecting us?
            5. If they want to hire someone, provide a brief job description. Otherwise, state "No hiring request."

            Keep the response short, professional, and easy to understand.
            """

            payload = {
                'text': prompt,
                'email': email_from,
                'image_base64': None
            }

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }

            _logger.info("📡 Gửi yêu cầu phân tích AI...")
            response = requests.post("http://192.168.1.51:9999/api/status", json=payload, headers=headers, timeout=None)
            if response.status_code != 200:
                _logger.error(f"❌ Flask API trả về lỗi {response.status_code}: {response.text}")
                return {'error': f'API request failed with status {response.status_code}'}

            ai_result = response.json().get("result", "No result")
            ai_result_html = ai_result.replace("\n", "<br/>").replace("\r", "")

            comment_html = Markup(f"""
                <div>
                    <b>✉️ Nội dung Email:</b><br/>{html_body}
                    <hr/>
                    <b>🧠 GPT Phân Tích:</b><br/>{ai_result_html}
                </div>
            """)

            # Step 3: Tìm hoặc tạo partner
            partner = request.env['res.partner'].sudo().search([('email', '=', email_from)], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().search([('name', '=', sender_name)], limit=1)

            if not partner:
                _logger.info(f"👤 Tạo partner mới: {sender_name} - {email_from}")
                partner = request.env['res.partner'].sudo().create({
                    'name': sender_name or "No Name",
                    'email': email_from,
                })

            # Step 4: Tìm lead theo email_from và partner
            existing_leads = request.env['crm.lead'].sudo().search([
                ('partner_id', '=', partner.id),
                ('email_from', '=', email_from)
            ], order='create_date desc', limit=1)

            if existing_leads:
                lead = existing_leads
                _logger.info(f"✏️ Lead đã tồn tại, cập nhật nội dung. Lead ID={lead.id}")

                # 👉 Nếu có body_analyze cũ, đưa vào comment
                if lead.body_analyze:
                    lead.message_post(
                        body=lead.body_analyze,
                        message_type="comment",
                        subtype_xmlid="mail.mt_note"
                    )

                # 👉 Cập nhật body_analyze với nội dung GPT mới
                lead.body_analyze = comment_html
                lead.reply_email = html_body or ""
                lead.message_id = message_id or ""

                lead_note = '✏️ Đã cập nhật nội dung GPT cho lead cũ và lưu nội dung cũ vào comment'

            else:
                # 🆕 Tạo lead mới nếu không có
                lead_vals = {
                    'name': subject,
                    'email_from': email_from,
                    'partner_id': partner.id,
                    'reply_email': html_body,
                    'message_id': message_id,
                    'body_analyze': comment_html,
                }

                _logger.debug(f"🆕 Lead values: {lead_vals}")
                _logger.info(f"🛠️ Đang tạo lead mới cho partner {partner.name} ({partner.email})")

                lead = request.env['crm.lead'].sudo().create(lead_vals)
                lead_note = '🆕 Tạo lead mới cho partner'

            _logger.info(f"🏁 Kết thúc xử lý email. Lead ID: {lead.id}, Partner: {partner.name} ({partner.email})")
            _logger.info(f"🧠 Kết quả GPT (tối đa 300 ký tự): {repr(ai_result[:300])}")

            return {
                'success': True,
                'result': ai_result,
                'lead_id': lead.id,
                'message': f'✅ {lead_note}'
            }

        except requests.exceptions.RequestException as e:
            _logger.error(f"❌ Kết nối đến Flask thất bại: {str(e)}")
            return {'error': f'Failed to connect to analysis service: {str(e)}'}

        except Exception as e:
            _logger.exception("❌ Lỗi không xác định khi xử lý email:")
            return {'error': f'Unexpected error: {str(e)}'}