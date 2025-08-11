from odoo import models, fields, api


class GmailSync(models.Model):
    _name = "custom_gmail.gmail.sync"
    _description = "Gmail Sync Model"

    name = fields.Char(string="Name")

    def redirect_to_gmail_messages(self):
        return {
            "type": "ir.actions.client",
            "tag": "gmail_inbox_ui",
            "name": "Gmail Inbox",
            "target": "current",
        }
