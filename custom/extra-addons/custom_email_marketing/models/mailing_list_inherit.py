from odoo import models, fields

class MailingList(models.Model):
    _inherit = "mailing.list"

    start_date = fields.Date(string="Start Date", default=lambda self: fields.Date.context_today(self))


