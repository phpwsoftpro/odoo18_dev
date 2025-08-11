from odoo import models, api


class MailMail(models.Model):
    _inherit = "mail.mail"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "email_from" in vals:
                # Tìm Outgoing Mail Server mặc định
                outgoing_server = self.env["ir.mail_server"].search([], limit=1)
                if outgoing_server:
                    # Cập nhật tên gửi và reply-to theo Outgoing Mail Server
                    vals["email_from"] = (
                        f"{outgoing_server.name} <{outgoing_server.smtp_user}>"
                    )
                    vals["reply_to"] = (
                        f"{outgoing_server.name} <{outgoing_server.smtp_user}>"
                    )
        return super().create(vals_list)
