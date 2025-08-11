from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class MailingTrace(models.Model):
    _inherit = "mailing.trace"

    res_partner_id = fields.Many2one(
        "res.partner",
        string="Recipient Partner",
        compute="_compute_res_partner_id",
        store=True,
    )
    mailing_id = fields.Many2one("mailing.mailing", string="Mailing")
    mailing_subject = fields.Char(
        string="Mailing Subject", compute="_compute_subject", store=True
    )

    @api.depends("email")
    def _compute_res_partner_id(self):
        for trace in self:
            partner = self.env["res.partner"].search(
                [("email", "=", trace.email)], limit=1
            )
            trace.res_partner_id = partner

    @api.depends("mailing_id.subject")
    def _compute_subject(self):
        for trace in self:
            trace.mailing_subject = trace.mailing_id.subject or ""
