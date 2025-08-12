from odoo import models, fields, api


class MailingListFolder(models.Model):
    _name = "mailing.list.folder"
    _description = "Mailing List Folder"

    name = fields.Char(required=True)
    description = fields.Text()


class MailingList(models.Model):
    _inherit = "mailing.list"

    folder_id = fields.Many2one("mailing.list.folder", string="Folder")


class MailingMailing(models.Model):
    _inherit = "mailing.mailing"

    folder_id = fields.Many2one("mailing.list.folder", string="Folder")
