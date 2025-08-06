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
                return {'error': "❌ Không thể xác định địa chỉ email người gửi — không thể tạo partner."}

            # Step 1: 🔐 Lấy token từ Flask
            login_payload = {
                "email": "lebadung@wsoftpro.com",
                "password": "zLrA3pN7"
            }
            login_resp = requests.post("http://192.168.1.51:9999/login", json=login_payload, timeout=20)
            if login_resp.status_code != 200:
                _logger.error("Login to Flask failed")
                return {'error': 'Login to analysis service failed'}

            token = login_resp.json().get("token")
            if not token:
                return {'error': 'No token returned from login'}

            # Step 2: Gửi dữ liệu để GPT phân tích
            payload = {
                'text': email_text,
                'email': email_from,
                'image_base64': None
            }

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }

            api_url = "http://192.168.1.51:9999/api/status"
            response = requests.post(api_url, json=payload, headers=headers, timeout=None)

            if response.status_code != 200:
                _logger.error(f"Flask API returned {response.status_code}: {response.text}")
                return {'error': f'API request failed with status {response.status_code}'}

            ai_result = response.json().get("result", "No result")
            comment_html = Markup(f"""
                <div>
                    <b>✉️ Nội dung Email:</b><br/>{html_body}
                    <hr/>
                    <b>🧠 GPT Phân Tích:</b><br/>{ai_result}
                </div>
            """)

            # Step 3: Tìm partner theo email trước, sau đó tên
            partner = request.env['res.partner'].sudo().search([('email', '=', email_from)], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().search([('name', '=', sender_name)], limit=1)

            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': sender_name or "No Name",
                    'email': email_from,
                })

            # Step 4: Tìm lead gần nhất
            existing_leads = request.env['crm.lead'].sudo().search([
                ('partner_id', '=', partner.id)
            ], order='create_date desc', limit=1)

            if existing_leads:
                existing_leads.message_post(
                    body=comment_html,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note"
                )
                lead = existing_leads
                lead_note = '📌 Đã comment vào lead có sẵn của partner'
            else:
                _logger.warning(f"📋 Fields in crm.lead: {request.env['crm.lead'].fields_get().keys()}")
                lead_vals = {
                    'name': subject,
                    'email_from': email_from,
                    'partner_id': partner.id,
                    'description': html_body
                }
                
                lead = request.env['crm.lead'].sudo().create(lead_vals)

                lead.message_post(
                    body=comment_html,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note"
                )
                lead_note = '🆕 Tạo lead mới cho partner'

            _logger.info(f"✅ Phân tích thành công và xử lý lead ID: {lead.id}")

            return {
                'success': True,
                'result': ai_result,
                'lead_id': lead.id,
                'message': f'✅ {lead_note}'
            }

        except requests.exceptions.RequestException as e:
            _logger.error(f"Request to Flask API failed: {str(e)}")
            return {'error': f'Failed to connect to analysis service: {str(e)}'}

        except Exception as e:
            _logger.exception("❌ Lỗi không xác định:")
            return {'error': f'Unexpected error: {str(e)}'}
