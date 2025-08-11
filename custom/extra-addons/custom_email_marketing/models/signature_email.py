from odoo import models, api, _
import logging

_logger = logging.getLogger(__name__)


class MailComposer(models.TransientModel):
    _inherit = "mail.compose.message"

    def _get_signature_template(self):
        """Generate HTML signature template for current user"""
        user = self.env.user
        company = self.env.company

        signature_template = f"""
            <div style="margin-top: 20px; padding-top: 10px; border-top: 1px solid #e5e5e5;">
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
                <table cellpadding="0" cellspacing="0" style="font-family: Poppins, sans-serif; color: #333333; width: 100%; max-width: 600px;">
                    <tr>
                        <td style="width: 150px; vertical-align: top; padding-right: 20px;">
                            <img src="/web/image/res.company/{company.id}/logo" alt="{company.name}" style="width: 120px; height: auto;" />
                        </td>
                        <td style="vertical-align: top;">
                            <div style="font-size: 18px; font-weight: 650; margin-bottom: 5px;">Vanessa Ha</div>
                            <div style="color: black; margin-bottom: 5px; font-size: 15px; font-weight: 500;">Project Manager</div>
                            <div style="margin-bottom: 10px; font-weight: 600;">WSOFTPRO</div>
                            <hr />
                            <div style="margin: 4px 0;">
                                <span>📞</span> <a href="tel:+84393558941" style="color: black; margin-left: 10px; font-size: 15px;">(+84) 393 558 941</a>
                            </div>
                            <div style="margin: 4px 0;">
                                <span style="color: black">✉️</span> <a href="mailto:vanessa@wsoftpro.com" style="color: black; margin-left: 10px; font-size: 15px;">vanessa@wsoftpro.com</a>
                            </div>
                            <div style="margin: 4px 0;">
                                <span>🌐</span> <a href="https://wsoftpro.com/" target="_blank" style="color: black; margin-left: 10px; font-size: 15px;">https://wsoftpro.com/</a>
                            </div>
                            <div style="margin: 4px 0;">
                                <span>📍</span> <span style="color: black; margin-left: 10px; font-size: 15px;">7/26 Nguyen Hong, Dong Da, Hanoi, Vietnam</span>
                            </div>
                        </td>
                    </tr>
                </table>
            </div>
            """
        return signature_template

    def _add_signature_once(self, content):
        signature_html = self._get_signature_template()
        if signature_html not in content:
            return f"{content}<br>{signature_html}"
        return content

    @api.model
    def create(self, vals):
        """Gắn chữ ký khi tạo mới"""
        if vals.get("body") and not vals.get("template_id"):
            vals["body"] = self._add_signature_once(vals["body"])
        return super().create(vals)
