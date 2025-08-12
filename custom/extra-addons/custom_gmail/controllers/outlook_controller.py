from odoo import http
from odoo.http import request
import requests
import logging
from lxml import html
import re
import json
_logger = logging.getLogger(__name__)


class OutlookMessageController(http.Controller):
    @http.route("/outlook/messages", type="json", auth="user", csrf=False)
    def outlook_messages(self, folder="inbox", **kw):
        # 1) Lấy account + token
        account = (
            request.env["outlook.account"]
            .sudo()
            .search([("user_id", "=", request.env.user.id)], limit=1)
        )
        if not account:
            return {"status": "error", "message": "Outlook account not found"}

        access_token = account.outlook_access_token or ""
        refresh_token = account.outlook_refresh_token or ""

        # Lấy config để refresh (từ model cấu hình của bạn)
        cfg = request.env["outlook.mail.sync"].sudo().get_outlook_config()

        def _headers(tok):
            return {"Authorization": f"Bearer {tok}"}

        def _list(url, tok):
            return requests.get(url, headers=_headers(tok))

        def _detail(mid, tok):
            u = f"https://graph.microsoft.com/v1.0/me/messages/{mid}"
            return requests.get(u, headers=_headers(tok))

        # 2) Xác định URL list theo folder
        urls = []
        if folder in (None, "", "inbox"):
            urls.append(
                "https://graph.microsoft.com/v1.0/me/messages?$orderby=receivedDateTime desc&$top=20"
            )
        elif folder == "sent":
            urls.append(
                "https://graph.microsoft.com/v1.0/me/mailFolders('sentitems')/messages?$orderby=sentDateTime desc&$top=20"
            )
        elif folder == "all":
            urls.append(
                "https://graph.microsoft.com/v1.0/me/messages?$orderby=receivedDateTime desc&$top=20"
            )
            urls.append(
                "https://graph.microsoft.com/v1.0/me/mailFolders('sentitems')/messages?$orderby=sentDateTime desc&$top=20"
            )
        else:
            return {"status": "error", "message": f"Unknown folder: {folder}"}

        # 3) Gọi API lần đầu
        lists = []
        for list_url in urls:
            r = _list(list_url, access_token)
            # 3a) Nếu 401 -> refresh token rồi thử lại (reuse logic controller/drafts hoặc auth)
            if r.status_code == 401 and refresh_token:
                tk = requests.post(
                    "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                    data={
                        "client_id": cfg["client_id"],
                        "client_secret": cfg["client_secret"],
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "redirect_uri": cfg["redirect_uri"],
                        "scope": "https://graph.microsoft.com/.default",
                    },
                )
                if tk.status_code == 200:
                    tkj = tk.json()
                    new_access = tkj.get("access_token")
                    new_refresh = tkj.get("refresh_token") or refresh_token
                    if new_access:
                        account.write(
                            {
                                "outlook_access_token": new_access,
                                "outlook_refresh_token": new_refresh,
                            }
                        )
                        access_token = new_access  # dùng token mới cho các call sau
                        r = _list(list_url, access_token)
                    else:
                        return {"status": "error", "message": "Cannot refresh token"}
                else:
                    return {
                        "status": "error",
                        "message": "Outlook token expired. Please log in again.",
                    }

            if r.status_code != 200:
                return {"status": "error", "message": "Failed to fetch messages"}

            lists.append(r.json().get("value", []))

        # 4) Hợp nhất + lấy chi tiết từng mail để có full body HTML
        Message = request.env["outlook.message"].sudo()  # Lưu vào db
        full = []
        for idx, message_list in enumerate(lists):
            for msg in message_list:
                dr = _detail(msg["id"], access_token)
                if dr.status_code != 200:
                    continue
                d = dr.json()
                is_sent = bool(d.get("sentDateTime"))
                folder_hint = "sent" if ("sentitems" in urls[idx]) else "inbox"
                Message.upsert_from_graph_detail(
                    d, folder_hint=folder_hint, user_id=request.env.user.id
                )
                full.append(
                    {
                        "id": d["id"],
                        "subject": d.get("subject", "No Subject"),
                        "sender": d.get("sender", {})
                        .get("emailAddress", {})
                        .get("name"),
                        "from": d.get("from", {})
                        .get("emailAddress", {})
                        .get("address"),
                        "date": (
                            d.get("sentDateTime")
                            if is_sent
                            else d.get("receivedDateTime")
                        ),
                        "folder": (
                            "sent" if is_sent or ("sentitems" in urls[idx]) else "inbox"
                        ),
                        "body_html": d.get("body", {}).get("content", "") or "",
                        "content_type": d.get("body", {}).get("contentType", "html"),
                        "type": "outlook",
                    }
                )

        # 5) Sort theo thời gian mới nhất
        full.sort(key=lambda m: m.get("date") or "", reverse=True)

        return {"status": "ok", "messages": full}

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

    @http.route(
        "/outlook/send_email", type="http", auth="user", methods=["POST"], csrf=False
    )
    def outlook_send_email(self, **kw):
        # Lấy tài khoản Outlook của user
        account = (
            request.env["outlook.account"]
            .sudo()
            .search([("user_id", "=", request.env.user.id)], limit=1)
        )
        if not account or not account.outlook_access_token:
            return request.make_response(
                json.dumps(
                    {"status": "error", "message": "Outlook account/token missing"}
                ),
                headers=[("Content-Type", "application/json")],
            )

        form = request.httprequest.form
        files = request.httprequest.files.getlist("attachments[]")

        to = (form.get("to") or "").strip()
        cc = (form.get("cc") or "").strip()
        bcc = (form.get("bcc") or "").strip()
        subject = form.get("subject") or ""
        body_html = form.get("body_html") or ""

        if not to:
            return request.make_response(
                json.dumps({"status": "error", "message": "Missing 'to'"}),
                headers=[("Content-Type", "application/json")],
            )

        # Build recipients
        def _emails(s):
            return [
                {"emailAddress": {"address": x.strip()}}
                for x in s.split(",")
                if x and x.strip()
            ]

        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body_html},
                "toRecipients": _emails(to),
            },
            "saveToSentItems": True,
        }
        if cc:
            payload["message"]["ccRecipients"] = _emails(cc)
        if bcc:
            payload["message"]["bccRecipients"] = _emails(bcc)

        # File attachments (Graph cần base64)
        attachments = []
        for f in files:
            content_bytes = base64.b64encode(f.read()).decode("ascii")
            attachments.append(
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": f.filename,
                    "contentBytes": content_bytes,
                    "contentType": f.mimetype or "application/octet-stream",
                }
            )
        if attachments:
            payload["message"]["attachments"] = attachments

        headers = {
            "Authorization": f"Bearer {account.outlook_access_token}",
            "Content-Type": "application/json",
        }
        url = "https://graph.microsoft.com/v1.0/me/sendMail"
        resp = requests.post(url, headers=headers, json=payload)

        # Refresh token nếu 401 (tái sử dụng logic refresh như /outlook/messages của bạn)
        if resp.status_code == 401 and account.outlook_refresh_token:
            cfg = request.env["outlook.mail.sync"].sudo().get_outlook_config()
            tk = requests.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "grant_type": "refresh_token",
                    "refresh_token": account.outlook_refresh_token,
                    "redirect_uri": cfg["redirect_uri"],
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            if tk.status_code == 200:
                j = tk.json()
                new_access = j.get("access_token")
                if new_access:
                    account.sudo().write(
                        {
                            "outlook_access_token": new_access,
                            "outlook_refresh_token": j.get("refresh_token")
                            or account.outlook_refresh_token,
                        }
                    )
                    headers["Authorization"] = f"Bearer {new_access}"
                    resp = requests.post(url, headers=headers, json=payload)

        if resp.status_code in (200, 202):
            return request.make_response(
                json.dumps({"status": "ok"}),
                headers=[("Content-Type", "application/json")]
            )
        return request.make_response(
            json.dumps({"status": "error", "message": resp.text}),
            headers=[("Content-Type", "application/json")],
            status=400
        )
    @http.route("/outlook/draft_messages", type="json", auth="user", csrf=False)
    def outlook_draft_messages(self, **kw):
        """Fetch draft emails from Outlook"""
        account = (
            request.env["outlook.account"]
            .sudo()
            .search([("user_id", "=", request.env.user.id)], limit=1)
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
                account.write(
                    {
                        "outlook_access_token": token,
                        "outlook_refresh_token": tk_j.get("refresh_token") or refresh,
                    }
                )
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
