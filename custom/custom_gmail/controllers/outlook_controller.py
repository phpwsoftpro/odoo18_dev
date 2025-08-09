from odoo import http
from odoo.http import request
import requests
import logging
from lxml import html
import re

_logger = logging.getLogger(__name__)


class OutlookMessageController(http.Controller):

    @http.route("/outlook/messages", type="json", auth="user", csrf=False)
    def outlook_messages(self, **kw):
        account = (
            request.env["outlook.account"].sudo().search(
                [("user_id", "=", request.env.user.id)], limit=1
            )
        )
        access_token = account.outlook_access_token if account else ""
        if not access_token:
            return {"status": "error", "message": "No Outlook access token found"}

        headers = {"Authorization": f"Bearer {access_token}"}
        list_url = "https://graph.microsoft.com/v1.0/me/messages?$orderby=receivedDateTime desc&$top=20"
        list_response = requests.get(list_url, headers=headers)

        if list_response.status_code != 200:
            _logger.error(f"❌ Failed to fetch message list: {list_response.text}")
            return {"status": "error", "message": "Failed to fetch messages"}

        message_list = list_response.json().get("value", [])
        full_messages = []

        for msg in message_list:
            msg_id = msg["id"]
            # detail_url = f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}?$select=subject,body,bodyPreview,receivedDateTime,from,sender"
            detail_url = f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}"
            detail_response = requests.get(detail_url, headers=headers)

            if detail_response.status_code == 200:
                detail = detail_response.json()
                full_messages.append(
                    {
                        "id": detail["id"],
                        "subject": detail.get("subject", "No Subject"),
                        "sender": detail.get("sender", {})
                        .get("emailAddress", {})
                        .get("name"),
                        "from": detail.get("from", {})
                        .get("emailAddress", {})
                        .get("address"),
                        "date": detail.get("receivedDateTime"),
                        "body": detail.get("body", {}).get("content", "No Content"),
                        "bodyPreview": detail.get("bodyPreview", ""),
                        "type": "outlook",  
                    }
                )
            else:
                _logger.warning(f"⚠️ Failed to fetch detail for message {msg_id}")

        return {"status": "ok", "messages": full_messages}

    @http.route("/outlook/sent_messages", type="json", auth="user", csrf=False)
    def outlook_sent_messages(self, **kw):
        """Fetch sent emails from Outlook"""
        account = (
            request.env["outlook.account"].sudo().search(
                [("user_id", "=", request.env.user.id)], limit=1
            )
        )
        access_token = account.outlook_access_token if account else ""
        if not access_token:
            return {"status": "error", "message": "No Outlook access token found"}

        headers = {"Authorization": f"Bearer {access_token}"}
        list_url = (
            "https://graph.microsoft.com/v1.0/me/mailFolders('sentitems')/messages"
            "?$orderby=sentDateTime desc&$top=20"
        )
        list_response = requests.get(list_url, headers=headers)

        if list_response.status_code != 200:
            _logger.error(
                f"❌ Failed to fetch sent message list: {list_response.text}"
            )
            return {"status": "error", "message": "Failed to fetch sent messages"}

        message_list = list_response.json().get("value", [])
        full_messages = []

        for msg in message_list:
            msg_id = msg["id"]
            detail_url = f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}"
            detail_response = requests.get(detail_url, headers=headers)

            if detail_response.status_code == 200:
                detail = detail_response.json()
                full_messages.append(
                    {
                        "id": detail["id"],
                        "subject": detail.get("subject", "No Subject"),
                        "sender": detail.get("sender", {})
                        .get("emailAddress", {})
                        .get("name"),
                        "from": detail.get("from", {})
                        .get("emailAddress", {})
                        .get("address"),
                        "date": detail.get("sentDateTime"),
                        "body": detail.get("body", {}).get("content", "No Content"),
                        "bodyPreview": detail.get("bodyPreview", ""),
                        "type": "outlook",
                    }
                )
            else:
                _logger.warning(f"⚠️ Failed to fetch detail for message {msg_id}")

        return {"status": "ok", "messages": full_messages}

    @http.route("/outlook/current_user_info", type="json", auth="user")
    def outlook_current_user_info(self):
        account = (
            request.env["outlook.account"]
            .sudo()
            .search([("user_id", "=", request.env.user.id)], limit=1)
        )
        access_token = account.outlook_access_token if account else ""

        if not access_token:
            return {"status": "error", "message": "No access token"}

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        response = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)

        if response.status_code != 200:
            return {"status": "error", "message": "Failed to fetch user info"}

        user_info = response.json()
        email = user_info.get("mail") or user_info.get("userPrincipalName")
        return {"status": "success", "email": email}

    @http.route("/outlook/my_accounts", type="json", auth="user")
    def my_outlook_accounts(self):
        accounts = (
            request.env["outlook.account"]
            .sudo()
            .search(
                [
                    ("user_id", "=", request.env.user.id),
                ]
            )
        )
        return [
            {
                "id": acc.id,
                "email": acc.email,
                "name": (acc.email or "").split("@")[0] if acc.email else "Unknown",
                "initial": (acc.email or "X")[0].upper(),
                "status": "active",
                "type": "outlook",
            }
            for acc in accounts
        ]

    @http.route("/outlook/delete_account", type="json", auth="user", csrf=False)
    def delete_outlook_account(self, account_id):
        account = (
            request.env["outlook.account"]
            .sudo()
            .search(
                [
                    ("id", "=", account_id),
                    ("user_id", "=", request.env.user.id),
                ],
                limit=1,
            )
        )

        if account:
            account.unlink()
            return {"status": "deleted"}
        return {"status": "not_found"}

    @http.route("/outlook/message_detail", type="json", auth="user")
    def outlook_message_detail(self, message_id):
        account = (
            request.env["outlook.account"]
            .sudo()
            .search([("user_id", "=", request.env.user.id)], limit=1)
        )

        if not account:
            return {"status": "error", "message": "Outlook account not found"}

        access_token = account.outlook_access_token

        if not access_token:
            return {"status": "error", "message": "No Outlook access token found"}

        url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            _logger.error(f"❌ Failed to fetch Outlook message detail: {response.text}")
            return {"status": "error", "message": "Failed to fetch message detail"}

        message = response.json()
        raw_body = message.get("body", {}).get("content", "")

        # 👉 Strip Word-style CSS, HTML, and extract clean text
        try:
            # 1. Replace <br> with newline (optional)
            raw_body = (
                raw_body.replace("<br>", "\n")
                .replace("<br/>", "\n")
                .replace("<br />", "\n")
            )

            # 2. Remove style/comments (e.g., <!-- ... -->)
            raw_body = re.sub(r"<!--.*?-->", "", raw_body, flags=re.DOTALL)

            # 3. Parse and extract plain text
            parsed = html.fromstring(raw_body)
            cleaned_body = parsed.text_content()
        except Exception:
            cleaned_body = raw_body  # fallback if parsing fails

        return {
            "status": "ok",
            "subject": message.get("subject"),
            "sender": message.get("sender", {}).get("emailAddress", {}).get("name"),
            "from": message.get("from", {}).get("emailAddress", {}).get("address"),
            "date": message.get("receivedDateTime"),
            "body": cleaned_body.strip(),  # 👉 plain text only
            "content_type": message.get("body", {}).get("contentType", "unknown"),
        }

    @http.route("/outlook/draft_messages", type="json", auth="user", csrf=False)
    def outlook_draft_messages(self, **kw):
        """Fetch draft emails from Outlook"""
        account = (
            request.env["outlook.account"].sudo().search([
                ("user_id", "=", request.env.user.id)
            ], limit=1)
        )

        if not account:
            return {"status": "error", "message": "Outlook account not found"}

        token = account.outlook_access_token
        refresh = account.outlook_refresh_token

        def _fetch(tok):
            url = (
                "https://graph.microsoft.com/v1.0/me/mailFolders('drafts')/messages"
                "?$orderby=lastModifiedDateTime desc&$top=20"
            )
            return requests.get(url, headers={"Authorization": f"Bearer {tok}"})

        resp = _fetch(token)
        if resp.status_code == 401 and refresh:
            cfg = request.env["outlook.mail.sync"].sudo().get_outlook_config()
            tk_resp = requests.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "redirect_uri": cfg["redirect_uri"],
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            if tk_resp.status_code == 200:
                tk_j = tk_resp.json()
                token = tk_j.get("access_token")
                account.write({
                    "outlook_access_token": token,
                    "outlook_refresh_token": tk_j.get("refresh_token") or refresh,
                })
                resp = _fetch(token)
            else:
                return {"status": "error", "message": "Outlook token expired"}

        if resp.status_code != 200:
            _logger.error("❌ Failed to fetch Outlook drafts: %s", resp.text)
            return {"status": "error", "message": "Failed to fetch drafts"}

        messages = resp.json().get("value", [])
        return {
            "status": "ok",
            "messages": [
                {
                    "id": m["id"],
                    "message_id": m.get("internetMessageId"),
                    "thread_id": m.get("conversationId"),
                    "subject": m.get("subject", "No Subject"),
                    "from": m.get("from", {}).get("emailAddress", {}).get("address"),
                    "date": m.get("lastModifiedDateTime"),
                    "bodyPreview": m.get("bodyPreview", ""),
                    "type": "outlook",
                }
                for m in messages
            ],
        }
