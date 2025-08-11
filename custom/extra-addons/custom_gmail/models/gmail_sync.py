# import requests
# import logging
# from odoo import models, api

# _logger = logging.getLogger(__name__)


# class GmailSync(models.Model):
#     _inherit = "mail.message"

#     @api.model
#     def scheduled_gmail_sync(self):
#         """
#         Scheduled action to fetch Gmail messages periodically.
#         Ensures the access token is valid or refreshes it if expired.
#         """
#         _logger.debug("Scheduled Gmail sync invoked.")

#         config = self.get_google_config()
#         access_token = (
#             self.env["ir.config_parameter"].sudo().get_param("gmail_access_token")
#         )

#         if not access_token:
#             _logger.error("Access token not available. Attempting to refresh token.")
#             refresh_token = (
#                 self.env["ir.config_parameter"].sudo().get_param("gmail_refresh_token")
#             )
#             if refresh_token:
#                 _logger.debug("Refreshing access token using refresh token.")
#                 payload = {
#                     "client_id": config["client_id"],
#                     "client_secret": config["client_secret"],
#                     "refresh_token": refresh_token,
#                     "grant_type": "refresh_token",
#                 }
#                 response = requests.post(config["token_uri"], data=payload)
#                 _logger.debug("Refresh token response: %s", response.text)

#                 if response.status_code == 200:
#                     token_data = response.json()
#                     access_token = token_data.get("access_token")
#                     self.env["ir.config_parameter"].sudo().set_param(
#                         "gmail_access_token", access_token
#                     )
#                     _logger.info("Access token refreshed successfully.")
#                 else:
#                     _logger.error("Failed to refresh access token: %s", response.text)
#                     return
#             else:
#                 _logger.error(
#                     "Refresh token not available. Cannot sync Gmail messages."
#                 )
#                 return

#         try:
#             gmail_messages = self.sudo().fetch_gmail_messages(access_token)
#             current_partner_id = self.env.user.partner_id.id
#             discuss_channel = (
#                 self.env["discuss.channel"]
#                 .sudo()
#                 .search([("name", "=", "Inbox")], limit=1)
#             )

#             if not discuss_channel:
#                 _logger.debug("Creating Discuss Inbox channel.")
#                 discuss_channel = (
#                     self.env["discuss.channel"]
#                     .sudo()
#                     .create(
#                         {
#                             "name": "Inbox",
#                             "channel_type": "chat",
#                             "channel_partner_ids": [(4, current_partner_id)],
#                         }
#                     )
#                 )

#             for message in gmail_messages:
#                 try:
#                     _logger.info(
#                         "Creating Discuss message for Gmail ID: %s", message["id"]
#                     )
#                     created_message = self.sudo().create(
#                         {
#                             "gmail_id": message["id"],
#                             "subject": message["subject"] or "No Subject",
#                             "body": message["body"] or "No Body",
#                             "message_type": "email",
#                             "model": "discuss.channel",
#                             "res_id": discuss_channel.id,
#                             "author_id": current_partner_id,
#                         }
#                     )

#                     _logger.info(
#                         "Creating notification for Gmail ID: %s", message["id"]
#                     )
#                     self.env["mail.notification"].sudo().create(
#                         {
#                             "mail_message_id": created_message.id,
#                             "res_partner_id": current_partner_id,
#                             "notification_type": "inbox",
#                             "is_read": False,
#                         }
#                     )
#                 except Exception as e:
#                     _logger.error(
#                         "Failed to create Discuss message or notification for Gmail ID: %s. Error: %s",
#                         message["id"],
#                         str(e),
#                     )
#         except Exception as e:
#             _logger.error("Error during scheduled Gmail sync: %s", str(e))
