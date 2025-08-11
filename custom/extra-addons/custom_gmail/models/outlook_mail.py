import logging
import msal
import requests
from datetime import datetime, timedelta
from odoo import models, fields, api
import json
from bs4 import BeautifulSoup

_logger = logging.getLogger(__name__)


class OutlookMailSync(models.Model):
    _name = "outlook.mail.sync"
    _description = "Outlook Mail Synchronization"

    user_id = fields.Many2one("res.users", string="User")
    last_sync_date = fields.Datetime(string="Last Sync Date")
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="draft",
        string="Status",
    )

    @api.model
    def action_redirect_outlook_auth(self):
        config = self.get_outlook_config()

        scope = (
            "https://graph.microsoft.com/Mail.ReadWrite "
            "https://graph.microsoft.com/Mail.Read"
        )

        auth_url = (
            f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/authorize"
            f"?client_id={config['client_id']}"
            f"&response_type=code"
            f"&redirect_uri={config['redirect_uri']}"
            f"&response_mode=query"
            f"&scope={scope}"
            f"&prompt=consent"
        )

        return {
            "type": "ir.actions.act_url",
            "url": auth_url,
            "target": "new",
        }

    def get_outlook_config(self):
        Param = self.env["ir.config_parameter"].sudo()
        return {
            "client_id": Param.get_param("outlook_client_id"),
            "client_secret": Param.get_param("outlook_client_secret"),
            "tenant_id": Param.get_param("outlook_tenant_id"),
            "redirect_uri": Param.get_param("outlook_redirect_uri"),
            "auth_uri": f"https://login.microsoftonline.com/{Param.get_param('outlook_tenant_id')}/oauth2/v2.0/authorize",
            "token_uri": f"https://login.microsoftonline.com/{Param.get_param('outlook_tenant_id')}/oauth2/v2.0/token",
        }

    def create_sync_job(self, user_id):
        """Create and run a new sync job for a user."""
        sync_job = self.create(
            {
                "user_id": user_id,
                "status": "running",
            }
        )

        try:
            # Get auth code from user
            account = self.env["outlook.account"].search(
                [("user_id", "=", user_id)], limit=1
            )
            auth_code = account.outlook_auth_code if account else ""

            if not auth_code:
                sync_job.write({"status": "failed"})
                return False

            # Get token from auth code
            config = self.get_outlook_config()
            app = msal.ConfidentialClientApplication(
                config["client_id"],
                authority=f"https://login.microsoftonline.com/{config['tenant_id']}",
                client_credential=config["client_secret"],
            )

            token_response = app.acquire_token_by_authorization_code(
                code=auth_code,
                scopes=[
                    "https://graph.microsoft.com/Mail.ReadWrite",
                    "https://graph.microsoft.com/Mail.Read",
                ],
                redirect_uri=config["redirect_uri"],
            )

            if "access_token" not in token_response:
                _logger.error(
                    f"Error getting token: {token_response.get('error_description', '')}"
                )
                sync_job.write({"status": "failed"})
                return False

            # Get emails from Outlook
            headers = {
                "Authorization": f"Bearer {token_response['access_token']}",
                "Content-Type": "application/json",
            }

            # Get emails from the last 7 days
            date_from = (datetime.now() - timedelta(days=7)).strftime(
                "%Y-%m-%dT00:00:00Z"
            )

            endpoint = "https://graph.microsoft.com/v1.0/me/messages"
            params = {
                "$top": 50,
                "$select": "id,subject,receivedDateTime,from,toRecipients,bodyPreview,body,importance",
                "$orderby": "receivedDateTime DESC",
                "$filter": f"receivedDateTime ge {date_from}",
            }

            response = requests.get(endpoint, headers=headers, params=params)

            if response.status_code != 200:
                _logger.error(
                    f"Error fetching emails: {response.status_code} - {response.text}"
                )
                sync_job.write({"status": "failed"})
                return False

            outlook = response.json()
            html_body = outlook.get("body", {}).get("content", "")
            plain_text = BeautifulSoup(html_body, "html.parser").get_text()
            _logger.info(f"Plain text body: {plain_text}")
            _logger.info("Emails data:\n%s", json.dumps(outlook, indent=2))

        except Exception as e:
            _logger.error(f"Error syncing emails: {str(e)}")
            sync_job.write({"status": "failed"})
            return False
