from odoo import models, fields, api
import logging
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
    body_analyze = fields.Html(string="Reply Email", sanitize=False)
    template_ai = fields.Many2one('template.prompt', string="Template AI")


    @api.onchange('template_ai')
    def _onchange_template_ai(self):
        if self.template_ai:
            self.reply_email = self.template_ai.template_body
            # prompt = f"""
            # Bạn là trợ lý AI tạo nội dung email phản hồi.
            #
            # Nội dung gốc để phân tích:
            # {self.body_analyze}
            #
            # Từ khóa cần xuất hiện: {self.reply_email}
            # 👉 Yêu cầu:
            # - Chỉ trả về nội dung thư phản hồi (dưới dạng HTML Fields của odoo phân chia bố cục đẹp).
            # - Không được lặp lại nội dung yêu cầu hoặc bất kỳ hướng dẫn nào..".
            # """
            #
            # res = self.env['discuss.channel']._artificial_intelligence_options(prompt)
            # if res:
            #     self.reply_email = res
            # else:
            #     self.reply_email = "<p><i>Không có phản hồi từ AI</i></p>"  # fallback nếu AI không trả lời


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
