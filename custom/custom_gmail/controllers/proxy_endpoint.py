# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import requests
import logging
from markupsafe import Markup
import json
import re

_logger = logging.getLogger(__name__)

# ===== Danh sách stage chuẩn theo pipeline của bạn =====
KNOWN_STAGES = [
    "Recruitment",
    "Reply Client",
    "Estimate Project",
    "Proposition/ Trung Check",
    "Checking Meeting",
    "Send Email to Client",
    "Email Done",
    "Enrich/Follow-up/ Other",
    "Done Follow-up Email",
    "Reject",
]

def _normalize_stage_name(s):
    """Chuẩn hóa tên stage GPT trả về về đúng tên trong KNOWN_STAGES."""
    if not s:
        return None
    s = re.sub(r"\s+", " ", str(s)).strip()
    s_low = s.lower()

    # Map các synonym/keyword phổ biến
    mapping = {
        "recruitment": "Recruitment",
        "reply client": "Reply Client",
        "estimate project": "Estimate Project",
        "proposition": "Proposition/ Trung Check",
        "proposition/ trung check": "Proposition/ Trung Check",
        "checking meeting": "Checking Meeting",
        "send email to client": "Send Email to Client",
        "email done": "Email Done",
        "enrich": "Enrich/Follow-up/ Other",
        "follow-up": "Enrich/Follow-up/ Other",
        "enrich/follow-up/ other": "Enrich/Follow-up/ Other",
        "done follow-up email": "Done Follow-up Email",
        "reject": "Reject",
        # VN keywords
        "tuyển": "Recruitment",
        "tuyen": "Recruitment",
        "báo giá": "Proposition/ Trung Check",
        "bao gia": "Proposition/ Trung Check",
        "đề xuất": "Proposition/ Trung Check",
        "de xuat": "Proposition/ Trung Check",
        "họp": "Checking Meeting",
        "hop": "Checking Meeting",
        "gửi email": "Send Email to Client",
        "gui email": "Send Email to Client",
        "từ chối": "Reject",
        "tu choi": "Reject",
    }

    for k, v in mapping.items():
        if k in s_low:
            return v

    for name in KNOWN_STAGES:
        if s_low == name.lower():
            return name

    return None

def _find_stage_id(env, stage_name, team_id=None):
    """Tìm stage theo tên và team (team rỗng hoặc đúng team)."""
    if not stage_name:
        return False
    domain = [('name', '=', stage_name)]
    domain = domain + ['|', ('team_id', '=', False), ('team_id', '=', team_id or False)]
    stage = env['crm.stage'].sudo().search(domain, limit=1)
    return stage.id or False

def _extract_json(s):
    """Bóc JSON kể cả khi GPT bọc ```json ... ```."""
    if not s:
        return None
    s = str(s).strip()
    if s.startswith("```"):
        # bỏ ```json ... ```
        s = s.strip('`').strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    try:
        return json.loads(s)
    except Exception:
        return None


class EmailAnalyzeController(http.Controller):

    @http.route('/analyze_email_proxy', type='json', auth='public', methods=['POST'], csrf=False)
    def analyze_email_proxy(self):
        # Simple API key
        if request.httprequest.headers.get('X-API-KEY') != 'my-secret-key':
            return {'error': 'Invalid API key'}

        try:
            data = request.params

            email_text = (data.get('text') or '').strip()
            subject = data.get('subject') or 'No Subject'
            sender_name = data.get('sender_name') or 'Người gửi không xác định'
            email_from = (data.get('email_from') or 'unknown@example.com').strip()
            html_body = data.get('html_body') or email_text
            message_id = (data.get('message_id') or '').strip()

            if not email_text:
                return {'error': 'No email body provided'}

            if not email_from or email_from.lower() == "unknown@example.com":
                _logger.warning("❌ Không xác định được email người gửi — Bỏ qua.")
                return {'error': "❌ Không thể xác định địa chỉ email người gửi — không thể tạo partner."}

            # ===== Step 1: Lấy token Flask =====
            login_payload = {"email": "lebadung@wsoftpro.com", "password": "zLrA3pN7"}
            _logger.info("🔐 Đang đăng nhập để lấy token...")
            login_resp = requests.post("http://192.168.1.51:9999/login", json=login_payload, timeout=20)
            if login_resp.status_code != 200:
                _logger.error("❌ Đăng nhập Flask thất bại")
                return {'error': 'Login to analysis service failed'}

            token = login_resp.json().get("token")
            if not token:
                _logger.error("❌ Không nhận được token từ Flask")
                return {'error': 'No token returned from login'}

            # ===== Step 2: Prompt yêu cầu trả JSON có stage + summary =====
            stage_list_str = "\n".join(f"- {s}" for s in KNOWN_STAGES)
            prompt = f"""
            Analyze the email and classify it into exactly one CRM stage from this list:
            {stage_list_str}
            
            Return a pure JSON object with fields ONLY:
            - "stage": one of the stage names above (exact text)
            - "confidence": float 0..1
            - "reason": short reason (max 200 chars)
            - "summary": a concise human-readable summary (2-4 sentences), HTML-safe (no code fences)
            
            DO NOT include any other text, only JSON.
            
            Email:
            Subject: {subject}
            From: {email_from}
            
            Content:
            {email_text}
            """.strip()

            payload = {'text': prompt, 'email': email_from, 'image_base64': None}
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}

            _logger.info("📡 Gửi yêu cầu phân tích AI (stage+summary JSON)...")
            response = requests.post("http://192.168.1.51:9999/api/status", json=payload, headers=headers, timeout=None)
            if response.status_code != 200:
                _logger.error(f"❌ Flask API trả về lỗi {response.status_code}: {response.text}")
                return {'error': f'API request failed with status {response.status_code}'}

            raw_ai = response.json().get("result", "") or ""
            parsed = _extract_json(raw_ai)

            ai_stage_name = None
            ai_confidence = 0.0
            ai_reason = ""
            ai_summary = ""

            if parsed:
                ai_stage_name = _normalize_stage_name(parsed.get("stage"))
                try:
                    ai_confidence = float(parsed.get("confidence") or 0)
                except Exception:
                    ai_confidence = 0.0
                ai_reason = parsed.get("reason") or ""
                ai_summary = parsed.get("summary") or ""
            else:
                _logger.warning("⚠️ GPT không trả JSON hợp lệ, fallback heuristic.")
                ai_stage_name = _normalize_stage_name(raw_ai)

            # Fallback xác định stage nếu vẫn None
            if not ai_stage_name:
                text_low = (email_text or "").lower()
                if any(k in text_low for k in ["hire", "recruit", "cv", "resume", "tuyển", "tuyen"]):
                    ai_stage_name = "Recruitment"
                elif any(k in text_low for k in ["quote", "quotation", "pricing", "báo giá", "bao gia", "đề xuất", "de xuat"]):
                    ai_stage_name = "Proposition/ Trung Check"
                elif any(k in text_low for k in ["reject", "not interested", "another vendor", "từ chối", "tu choi"]):
                    ai_stage_name = "Reject"
                else:
                    ai_stage_name = "Enrich/Follow-up/ Other"

            _logger.info(f"🧭 Stage GPT đề xuất: {ai_stage_name} (conf={ai_confidence:.2f})")

            # ===== Build HTML phân tích để hiển thị đẹp =====
            analysis_html = f"""
                <div>
                    <b>🔎 AI Summary:</b><br/>{(ai_summary or '—').replace('\n', '<br/>')}<br/><br/>
                    <b>Reason:</b> {(ai_reason or '—')}<br/>
                    <b>Stage:</b> {ai_stage_name or '—'} (conf: {ai_confidence:.2f})
                </div>
            """
            comment_html = Markup(f"""
                <div>
                    <b>✉️ Nội dung Email:</b><br/>{html_body}
                    <hr/>
                    <b>🧠 GPT Phân Tích:</b><br/>{analysis_html}
                </div>
            """)

            # ===== Step 3: Tìm/ tạo partner =====
            partner = request.env['res.partner'].sudo().search([('email', '=', email_from)], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().search([('name', '=', sender_name)], limit=1)
            if not partner:
                _logger.info(f"👤 Tạo partner mới: {sender_name} - {email_from}")
                partner = request.env['res.partner'].sudo().create({
                    'name': sender_name or "No Name",
                    'email': email_from,
                })

            # ===== Stage ID theo team (nếu có) =====
            team_id = request.env.context.get('default_team_id')  # tùy chỉnh nếu cần
            stage_id = _find_stage_id(request.env, ai_stage_name, team_id=team_id)
            if not stage_id:
                _logger.warning(f"⚠️ Không tìm thấy crm.stage tên '{ai_stage_name}'. Dùng stage mặc định.")

            # ===== Step 4: Luôn tạo lead mới với stage + phân tích =====
            lead_vals = {
                'name': subject,
                'email_from': email_from,
                'partner_id': partner.id,
                'reply_email': html_body,        # fields.Html (custom)
                'message_id': message_id,        # custom
                'body_analyze': analysis_html,   # fields.Html (custom)
            }
            if stage_id:
                lead_vals['stage_id'] = stage_id

            _logger.debug(f"🆕 Lead values: {lead_vals}")
            _logger.info(f"🛠️ Tạo lead mới ở stage '{ai_stage_name}' (ID={stage_id}) cho partner {partner.name} ({partner.email})")

            lead = request.env['crm.lead'].sudo().create(lead_vals)

            # Chatter note
            lead.message_post(
                body=comment_html,
                message_type="comment",
                subtype_xmlid="mail.mt_note"
            )

            _logger.info(f"🏁 Xong. Lead ID: {lead.id} — Stage: {ai_stage_name}")
            return {
                'success': True,
                'result': parsed or raw_ai,  # trả về JSON parsed nếu có
                'lead_id': lead.id,
                'stage': ai_stage_name,
                'confidence': ai_confidence,
                'message': f"✅ Created lead in stage '{ai_stage_name}'"
            }

        except requests.exceptions.RequestException as e:
            _logger.error(f"❌ Kết nối đến Flask thất bại: {str(e)}")
            return {'error': f'Failed to connect to analysis service: {str(e)}'}

        except Exception as e:
            _logger.exception("❌ Lỗi không xác định khi xử lý email:")
            return {'error': f'Unexpected error: {str(e)}'}
