from odoo import models, fields, api
import logging , re, requests
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)
from markupsafe import Markup


class TemplatePrompt(models.Model):
    _name = "template.prompt"
    _description = "AI Prompt Template"

    name = fields.Char(string="Prompt Title", required=True)
    template_body = fields.Html(string="Template Body", required=True, sanitize=False)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    message_id = fields.Char(string="Gmail Message-ID", copy=False)
    reply_email = fields.Html(string="Reply Email", sanitize=False)
    body_analyze = fields.Html(string="AI Analyze (HTML)", sanitize=False)  # Sửa lại nhãn cho rõ
    template_ai = fields.Many2one('template.prompt', string="Template AI")

    # ================== Helpers ==================
    def _strip_html(self, html_text):
        """Lấy text sạch từ HTML để đưa vào prompt."""
        if not html_text:
            return ""
        # loại tag
        text = re.sub(r'<[^>]+>', ' ', html_text)
        # gom khoảng trắng
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _call_ai(self, prompt_text, timeout=60):
        """Đăng nhập Flask -> gọi /api/status để sinh nội dung trả lời (HTML)."""
        LOGIN_URL = "http://192.168.1.51:9999/login"
        GEN_URL = "http://192.168.1.51:9999/api/status"
        login_payload = {"email": "lebadung@wsoftpro.com", "password": "zLrA3pN7"}

        _logger.info("[AI] Đăng nhập Flask để lấy token...")
        r = requests.post(LOGIN_URL, json=login_payload, timeout=20)
        if r.status_code != 200:
            _logger.error(f"[AI] Login thất bại: {r.status_code} {r.text}")
            raise UserError("Không đăng nhập được dịch vụ AI.")

        token = r.json().get("token")
        if not token:
            _logger.error("[AI] Không nhận được token từ Flask")
            raise UserError("Không nhận được token từ dịch vụ AI.")

        payload = {
            "text": prompt_text,
            "email": "noreply@example.com",
            "image_base64": None,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        _logger.info("[AI] Gọi API sinh nội dung reply (HTML)...")
        resp = requests.post(GEN_URL, json=payload, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            _logger.error(f"[AI] API trả lỗi {resp.status_code}: {resp.text}")
            raise UserError(f"Dịch vụ AI lỗi: {resp.status_code}")

        # Tùy service: nhiều bạn trả {"result": "..."}; điều chỉnh nếu khác
        result = resp.json().get("result", "")
        if not result:
            _logger.warning("[AI] Không có trường 'result' trong response.")
        return result or ""

    # ================== Onchange ==================
    @api.onchange('template_ai')
    def _onchange_template_ai(self):
        """Khi đổi template AI, sinh reply_email bằng AI dựa trên body_analyze + template_body."""
        for lead in self:
            if not lead.template_ai:
                continue

            # 1) Lấy nội dung phân tích (text sạch) + template yêu cầu (HTML)
            analyze_text = lead._strip_html(lead.body_analyze) or ""
            template_html = lead.template_ai.template_body or ""

            # 2) Tạo prompt rõ ràng: chỉ yêu cầu trả về HTML content cho Odoo field Html
            prompt = f"""
            Bạn là trợ lý AI viết email phản hồi lịch sự và chuyên nghiệp.
            
            # Bối cảnh (tóm tắt từ AI analyze ban đầu):
            {analyze_text}
            
            # Hướng dẫn soạn thư:
            - Sử dụng HTML nhẹ phù hợp với Odoo Html field: <p>, <br/>, <ul>, <ol>, <li>, <b>, <i>, <a>, <blockquote>.
            - Bố cục rõ ràng, có lời chào và chữ ký.
            - Ngắn gọn, mạch lạc (6-12 câu), dùng ngôi "chúng tôi".
            - Tuyệt đối KHÔNG trả lại hướng dẫn hay mã code fences.
            
            # Yêu cầu/Từ khóa/Ý chính cần bám theo (template đã chọn):
            {template_html}
            
            # Chỉ trả về NỘI DUNG EMAIL (HTML), KHÔNG kèm lời giải thích.
            """.strip()

            # 3) Gọi AI — nếu lỗi thì fallback dùng template
            try:
                ai_html = lead._call_ai(prompt_text=prompt, timeout=90)
                # Một số service có thể trả thêm text dư; cắt bỏ code fences nếu có
                ai_html = ai_html.strip()
                if ai_html.startswith("```"):
                    ai_html = ai_html.strip("`").strip()
                    # nếu có "html" ở đầu
                    if ai_html.lower().startswith("html"):
                        ai_html = ai_html[4:].strip()

                # Nếu response không có tag, bọc nhẹ để render đẹp
                if "<" not in ai_html:
                    ai_html = f"<p>{ai_html}</p>"

                lead.reply_email = ai_html

            except Exception as e:
                _logger.exception("[AI] Sinh reply thất bại, dùng template_html làm fallback.")
                # Fallback: đổ template để user tự chỉnh
                lead.reply_email = template_html or ""
                # Không raise để onchange không chặn UI
                # (nếu muốn hiển thị cảnh báo nhẹ, có thể dùng warning trên onchange)




    def write(self, vals):
        for lead in self:
            old_stage = lead.stage_id.id
            new_stage = vals.get('stage_id')
            if new_stage:
                new_stage = int(new_stage)
                if new_stage == 2 and old_stage != 2:
                    _logger.info(f"[CRM] Cơ hội '{lead.name}' chuyển sang Giai đoạn 2 - Tạo Task + Job")
                    # Tìm hoặc tạo project mặc định
                    default_project = self.env['project.project'].search(
                        [('name', '=', 'CRM Tasks Project')], limit=1
                    )
                    if not default_project:
                        _logger.info("[CRM] Không tìm thấy Project 'CRM Tasks Project' - đang tạo mới.")
                        default_project = self.env['project.project'].create({
                            'name': 'CRM Tasks Project',
                            'privacy_visibility': 'employees',  # hoặc 'portal' tùy ý
                            'allow_timesheets': False,
                        })

                    # Tạo task gắn project
                    task = self.env['project.task'].create({
                        'name': lead.name,
                        'description': lead.description or '',
                        'partner_id': lead.partner_id.id if lead.partner_id else False,
                        'project_id': default_project.id,
                    })
                    _logger.info(f"[CRM] Đã tạo Task (ID: {task.id}) cho cơ hội: {lead.name}")

                    # Tạo job gắn task
                    self.env['hr.job'].create({
                        'name': lead.name,
                        'description': lead.description or '',
                        'alias_name': lead.email_from,
                        'crm_task_id': task.id,
                    })
                    _logger.info(f"[CRM] Đã tạo Job gắn với Task (ID: {task.id}) cho cơ hội: {lead.name}")

                elif new_stage == 3 and old_stage != 3:  # Reply Client: server 7 and local 3
                    pass

                elif new_stage == 4 and old_stage != 4:  # Estimate Project: server 7 and local 2
                    pass

                elif new_stage == 5 and old_stage != 5:  # Proposition/ Trung Check: server 7 and local
                    pass

                elif new_stage == 6 and old_stage != 6:  # Checking Meeting: server 7 and local 2
                    pass

                elif new_stage == 7 and old_stage != 7:  # Send Email to Client: server 7 and local 2
                    pass

                elif new_stage == 8 and old_stage != 8:  # Email Done: server 7 and local 2
                    pass

                elif new_stage == 9 and old_stage != 9:  # Enrich/Follow-up/ Other: server 7 and local 2
                    pass

                elif new_stage == 10 and old_stage != 10:  # Done Follow-up Email/ Other: server 7 and local 2
                    pass

                elif new_stage == 11 and old_stage != 11:  # Reject: server 7 and local 2
                    pass

        return super(CrmLead, self).write(vals)

    def action_reply_email2(self):
        """Mở form nhập nội dung và Message-ID khi reply email"""
        wizard_model = self.env["send.task.email.wizard"]

        _logger.info(self.reply_email)
        _logger.info('test')

        signature = self.env["send.task.email.wizard"]._get_signature_template()
        clean_reply = f"{self.reply_email}\n\n\n{signature}"

        return {
            "type": "ir.actions.act_window",
            "name": "Reply Email",
            "res_model": wizard_model._name,
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_email_to": self.partner_id.email,
                "default_lead_id": self.id,
                "default_message_id": self.message_id,
                "default_email_subject": self.name,
                "default_body_html": clean_reply,
            },
        }
