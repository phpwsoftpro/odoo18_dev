from odoo import http
from odoo.http import request


class GmailSyncController(http.Controller):

    @http.route("/gmail/user_email", auth="user", type="json")
    def gmail_user_email(self):
        account = (
            request.env["gmail.account"]
            .sudo()
            .search([("user_id", "=", request.env.user.id)], limit=1)
        )
        gmail_email = account.gmail_authenticated_email if account else ""
        return {"gmail_email": gmail_email}

    @http.route("/outlook/user_email", auth="user", type="json")
    def outlook_user_email(self):
        account = (
            request.env["outlook.account"]
            .sudo()
            .search([("user_id", "=", request.env.user.id)], limit=1)
        )
        outlook_email = account.outlook_authenticated_email if account else ""
        return {"outlook_email": outlook_email}
