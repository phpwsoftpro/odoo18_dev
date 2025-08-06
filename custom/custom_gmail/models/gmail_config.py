import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class GmailConfig(models.Model):
    _inherit = "mail.message"

    @api.model
    def get_google_config(self):
        """
        Load Google API configuration for OAuth2.
        """
        _logger.debug("Loading Google API configuration.")
        return {
            "client_id": "608368888223-9pg2ov6ogn7155vj75m3d9avkt2unneu.apps.googleusercontent.com",
            "client_secret": "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",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            # "redirect_uri": "http://localhost:8070/odoo/gmail/auth/callback",
            "redirect_uri": "https://crm2.wsoftpro.com/odoo/gmail/auth/callback",
        }
