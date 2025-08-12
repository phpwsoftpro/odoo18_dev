from odoo import models


class MailMail(models.Model):
    _inherit = "mail.mail"

    def _action_send_mail(self, auto_commit=False):
        for mail in self:
            if (
                mail.reply_to
                and mail.reply_to.strip().lower() == mail.email_from.strip().lower()
            ):
                mail.reply_to = False  # Gỡ bỏ reply_to gây loop

        return super()._action_send_mail(auto_commit=auto_commit)
