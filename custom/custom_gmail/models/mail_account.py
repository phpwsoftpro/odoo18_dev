from odoo import models, fields, api


class GmailAccount(models.Model):
    _name = "gmail.account"
    _description = "Gmail Account"

    user_id = fields.Many2one("res.users", string="User", required=True)
    email = fields.Char(string="Email", required=True)
    access_token = fields.Char("Access Token")
    refresh_token = fields.Char("Refresh Token")
    token_expiry = fields.Datetime("Token Expiry")
    last_fetch_at = fields.Datetime(string="Last Fetch At")
