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
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uri": "http://localhost:8070/odoo/gmail/auth/callback",
            # "redirect_uri": "https://crm2.wsoftpro.com/odoo/gmail/auth/callback",
            # "redirect_uri": "https://ideal-system-x796vqr54jw2p76-8069.app.github.dev/odoo/gmail/auth/callback",
            "client_id": "934598997197-13d2tluslcltooi7253r1s1rkafj601h.apps.googleusercontent.com",
            "client_secret": "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",
        }
