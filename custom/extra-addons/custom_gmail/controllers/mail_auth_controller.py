import logging
import requests
import urllib
from datetime import datetime, timedelta
from odoo import http
from odoo.http import request
from werkzeug.utils import redirect

_logger = logging.getLogger(__name__)


class MailAuthController(http.Controller):

    # Khởi động OAuth
    @http.route("/<string:provider>/auth/start", type="http", auth="user")
    def mail_auth_start(self, provider, **kw):
        _logger.info(f"🔐 OAuth flow started for: {provider}")

        if provider == "gmail":
            config = request.env["mail.message"].sudo().get_google_config()
            scope = (
                "openid email "
                "https://www.googleapis.com/auth/gmail.readonly "
                "https://www.googleapis.com/auth/gmail.send "
                "https://www.googleapis.com/auth/gmail.compose"
            )
            params = {
                "client_id": config["client_id"],
                "redirect_uri": config["redirect_uri"],
                "response_type": "code",
                "access_type": "offline",
                "scope": scope,
                "prompt": "consent select_account",
                "include_granted_scopes": "false",
            }
            auth_url = f'{config["auth_uri"]}?{urllib.parse.urlencode(params)}'
            _logger.info(f"🔗 Redirecting to Google OAuth URL: {auth_url}")
            return redirect(auth_url)

        elif provider == "outlook":
            config = request.env["outlook.mail.sync"].sudo().get_outlook_config()
            params = {
                "client_id": config["client_id"],
                "response_type": "code",
                "redirect_uri": config["redirect_uri"],
                "response_mode": "query",
                "scope": "offline_access Mail.ReadWrite Mail.Read",
            }
            auth_url = f'https://login.microsoftonline.com/{config["tenant_id"]}/oauth2/v2.0/authorize?{urllib.parse.urlencode(params)}'
            _logger.info(f"🔗 Redirecting to Outlook OAuth URL: {auth_url}")
            return redirect(auth_url)

        else:
            _logger.error(f"❌ Invalid provider: {provider}")
            return "<h3>❌ Invalid provider.</h3>"

    # Callback xử lý code
    @http.route("/odoo/<string:provider>/auth/callback", type="http", auth="user")
    def mail_auth_callback(self, provider, **kw):
        _logger.info(f"📥 OAuth2 Callback từ: {provider} với params: {kw}")

        code = kw.get("code")
        if not code:
            return "<h3>❌ Missing authorization code.</h3>"

        if provider == "gmail":
            config = request.env["mail.message"].sudo().get_google_config()
            token_url = config["token_uri"]
            data = {
                "code": code,
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "redirect_uri": config["redirect_uri"],
                "grant_type": "authorization_code",
            }
            user_info_url = "https://openidconnect.googleapis.com/v1/userinfo"
            provider_name = "gmail"

        elif provider == "outlook":
            config = request.env["outlook.mail.sync"].sudo().get_outlook_config()
            token_url = config["token_uri"]
            data = {
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "code": code,
                "redirect_uri": config["redirect_uri"],
                "grant_type": "authorization_code",
            }
            user_info_url = "https://graph.microsoft.com/v1.0/me"
            provider_name = "outlook"

        else:
            return "<h3>❌ Invalid provider.</h3>"

        # Lấy Token
        token_res = requests.post(token_url, data=data)
        token_data = token_res.json()
        if "error" in token_data:
            return f"<h3>❌ Token Error: {token_data.get('error_description')}</h3>"

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        # Lấy Email người dùng
        user_info_res = requests.get(
            user_info_url, headers={"Authorization": f"Bearer {access_token}"}
        )
        user_info = user_info_res.json()

        if provider == "gmail":
            email = user_info.get("email")
        else:
            email = user_info.get("mail") or user_info.get("userPrincipalName")

        if not email:
            return "<h3>❌ Cannot retrieve email address.</h3>"

        # Lưu vào gmail.account
        account_model = request.env["gmail.account"].sudo()
        account = account_model.search(
            [
                ("user_id", "=", request.env.user.id),
                ("email", "=", email),
                ("provider", "=", provider_name),
            ],
            limit=1,
        )

        vals = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expiry": datetime.utcnow() + timedelta(seconds=expires_in),
        }

        if account:
            account.write(vals)
        else:
            vals.update(
                {
                    "user_id": request.env.user.id,
                    "email": email,
                    "provider": provider_name,
                }
            )
            account_model.create(vals)

        _logger.info(
            f"✅ {provider_name.capitalize()} account {email} linked successfully!"
        )

        return f"""
            <html><body>
                <script>
                    window.opener.postMessage("{provider}-auth-success", "*");
                    window.close();
                </script>
                <p>{provider_name.capitalize()} connected successfully...</p>
            </body></html>
        """
