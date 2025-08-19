from odoo.http import request
import requests
import logging
from lxml import html
import re
import json
import base64
from odoo import http, fields

_logger = logging.getLogger(__name__)


class OutlookMessageController(http.Controller):
    @http.route("/outlook/messages", type="json", auth="user", csrf=False)
    def outlook_messages(self, folder="inbox", page=1, limit=20, account_id=None, **kw):
        # 1) Lấy đúng account + token
        dom = [("user_id", "=", request.env.user.id)]
        if account_id:
            try:
                dom.append(("id", "=", int(account_id)))
            except Exception:
                pass
        account = request.env["outlook.account"].sudo().search(dom, limit=1)
        if not account:
            return {"status": "error", "message": "Outlook account not found"}

        access_token = account.outlook_access_token or ""
        refresh_token = account.outlook_refresh_token or ""

        cfg = request.env["outlook.mail.sync"].sudo().get_outlook_config()

        def _headers(tok):
            return {
                "Authorization": f"Bearer {tok}",
                "Prefer": 'outlook.body-content-type="html"',
                "ConsistencyLevel": "eventual",
                "Content-Type": "application/json",
            }

        # 2) Chuẩn hoá page/limit
        try:
            page = int(page or 1)
            limit = max(1, min(int(limit or 20), 50))
        except Exception:
            page, limit = 1, 20
        skip = (page - 1) * limit

        # 3) URL theo folder
        select_fields = (
            "id,subject,receivedDateTime,sentDateTime,from,sender,"
            "toRecipients,ccRecipients,bodyPreview,body,conversationId,internetMessageId"
        )

        inbox_url = (
            "https://graph.microsoft.com/v1.0/me/mailFolders('inbox')/messages"
            f"?$orderby=receivedDateTime desc&$top={limit}&$skip={skip}"
            f"&$select={select_fields}&$count=true"
        )
        sent_url = (
            "https://graph.microsoft.com/v1.0/me/mailFolders('sentitems')/messages"
            f"?$orderby=sentDateTime desc&$top={limit}&$skip={skip}"
            f"&$select={select_fields}&$count=true"
        )

        urls = []
        if folder in (None, "", "inbox"):
            urls.append(inbox_url)
        elif folder == "sent":
            urls.append(sent_url)
        elif folder == "all":
            urls.append(inbox_url)
            urls.append(sent_url)
        else:
            return {"status": "error", "message": f"Unknown folder: {folder}"}

        # 4) Gọi Graph (kèm refresh), fallback nếu 400 do $skip
        lists, totals = [], []
        for list_url in urls:
            r = requests.get(list_url, headers=_headers(access_token))

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
                        account.sudo().write(
                            {
                                "outlook_access_token": new_access,
                                "outlook_refresh_token": new_refresh,
                            }
                        )
                        access_token = new_access
                        r = requests.get(list_url, headers=_headers(access_token))
                    else:
                        return {"status": "error", "message": "Cannot refresh token"}
                else:
                    return {
                        "status": "error",
                        "message": "Outlook token expired. Please log in again.",
                    }

            if r.status_code == 400 and "$skip=" in list_url:
                url_no_skip = re.sub(r"&\$skip=\d+", "", list_url)
                r = requests.get(url_no_skip, headers=_headers(access_token))

            if r.status_code != 200:
                return {"status": "error", "message": "Failed to fetch messages"}

            j = r.json()
            lists.append(j.get("value", []))
            totals.append(j.get("@odata.count"))

        # 5) Upsert cache + build response
        Message = request.env["outlook.message"].sudo()
        full = []
        for idx, message_list in enumerate(lists):
            for d in message_list:
                is_sent = bool(d.get("sentDateTime"))
                folder_hint = "sent" if ("sentitems" in urls[idx]) else "inbox"

                # upsert DB
                try:
                    Message.upsert_from_graph_detail(
                        d,
                        folder_hint=folder_hint,
                        user_id=request.env.user.id,
                        account_id=account.id,
                        account_email=account.email,
                    )
                except Exception:
                    _logger.exception(
                        "Upsert Outlook message failed id=%s", d.get("id")
                    )

                def _recips(lst):
                    out = []
                    for r in lst or []:
                        ea = (r or {}).get("emailAddress") or {}
                        out.append(
                            {
                                "name": ea.get("name") or "",
                                "address": ea.get("address") or "",
                            }
                        )
                    return out

                def _join(lst):
                    items = []
                    for it in lst or []:
                        nm, ad = it.get("name") or "", it.get("address") or ""
                        if ad:
                            items.append(f"{nm} <{ad}>" if nm else ad)
                    return ", ".join(items)

                to_list = _recips(d.get("toRecipients"))
                cc_list = _recips(d.get("ccRecipients"))

                # tên người gửi hiển thị
                display_sender = (
                    ((d.get("from") or {}).get("emailAddress") or {}).get("name")
                    or ((d.get("sender") or {}).get("emailAddress") or {}).get("name")
                    or "Unknown Sender"
                )
                from_addr = ((d.get("from") or {}).get("emailAddress") or {}).get(
                    "address"
                ) or ""

                full.append(
                    {
                        "id": d["id"],
                        "subject": d.get("subject", "No Subject"),
                        "sender": display_sender,
                        "email_sender": from_addr,
                        "from": from_addr,
                        "to": to_list,  # list {name,address}
                        "cc": cc_list,  # list {name,address}
                        "email_receiver": _join(to_list),  # chuỗi cho FE dùng chung
                        "email_cc": _join(cc_list),
                        "date": (
                            d.get("sentDateTime")
                            if is_sent
                            else d.get("receivedDateTime")
                        ),
                        "folder": (
                            "sent" if is_sent or ("sentitems" in urls[idx]) else "inbox"
                        ),
                        "body_html": (d.get("body") or {}).get("content") or "",
                        "content_type": (d.get("body") or {}).get(
                            "contentType", "html"
                        ),
                        "type": "outlook",
                        # 🔴 thêm thông tin hội thoại
                        "thread_id": d.get("conversationId")
                        or d.get("internetMessageId")
                        or d.get("id"),
                        "conversationId": d.get("conversationId"),
                        "internetMessageId": d.get("internetMessageId"),
                    }
                )

        full.sort(key=lambda m: m.get("date") or "", reverse=True)

        total = None
        if len(totals) == 1 and isinstance(totals[0], int):
            total = totals[0]
        elif len(totals) == 2:
            total = sum(t for t in totals if isinstance(t, int))

        return {
            "status": "ok",
            "messages": full,
            "total": total,
            "page": page,
            "limit": limit,
        }

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
            # Trả về body dạng HTML
            "Prefer": 'outlook.body-content-type="html"',
        }
        # Lấy đủ trường cần thiết
        params = {
            "$select": "id,subject,from,sender,toRecipients,ccRecipients,conversationId,"
            "internetMessageId,sentDateTime,receivedDateTime,body,isRead"
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            _logger.error(
                "❌ Failed to fetch Outlook message detail: %s", response.text
            )
            return {"status": "error", "message": "Failed to fetch message detail"}

        m = response.json()
        body_html = (m.get("body") or {}).get("content") or ""

        # (tùy chọn) upsert cache
        try:
            request.env["outlook.message"].sudo().upsert_from_graph_detail(
                m,
                folder_hint="sent" if m.get("sentDateTime") else "inbox",
                user_id=request.env.user.id,
                account_id=account.id,
            )
        except Exception:
            _logger.exception(
                "Upsert Outlook message detail failed for id=%s", m.get("id")
            )

        def _addr(obj, key):
            return (obj or {}).get("emailAddress", {}).get(key)

        return {
            "status": "ok",
            "id": m["id"],
            "thread_id": m.get("conversationId"),
            "subject": m.get("subject"),
            "from": _addr(m.get("from"), "address"),
            "sender": _addr(m.get("sender"), "name"),
            "sentDateTime": m.get("sentDateTime"),
            "receivedDateTime": m.get("receivedDateTime"),
            "content_type": (m.get("body") or {}).get("contentType", "html"),
            "body_html": body_html,
            "is_read": m.get("isRead"),
        }

    @http.route("/outlook/thread_detail", type="json", auth="user", csrf=False)
    def outlook_thread_detail_db_first(
        self, thread_id=None, conversation_id=None, account_id=None
    ):
        thread_id = thread_id or conversation_id
        if not thread_id:
            return {"status": "error", "message": "Missing thread_id"}

        # Lấy đúng account của user + id thật trong DB
        dom_acc = [("user_id", "=", request.env.user.id)]
        if account_id:
            try:
                dom_acc.append(("id", "=", int(account_id)))
            except Exception:
                pass
        account = request.env["outlook.account"].sudo().search(dom_acc, limit=1)
        if not account:
            return {"status": "error", "message": "Outlook account not found"}

        Message = request.env["outlook.message"].sudo()
        acc_email = (account.email or "").strip().lower()

        # 1) Đọc DB trước
        recs = Message.search(
            [("thread_id", "=", thread_id), ("account_id", "=", account.id)],
            order="date asc, id asc",
        )

        # 2) Nếu chưa có thư do chính mình gửi (folder=sent hoặc from=account.email) => hydrate từ Graph
        def _has_my_sent(rs):
            for r in rs:
                if r.folder == "sent":
                    return True
                if (r.sender_address or "").strip().lower() == acc_email:
                    return True
            return False

        if not recs or not _has_my_sent(recs):
            self._hydrate_conversation_from_graph(thread_id, account)  # lấp cache
            recs = Message.search(
                [("thread_id", "=", thread_id), ("account_id", "=", account.id)],
                order="date asc, id asc",
            )

        # 3) Build JSON trả về
        def _fmt_dt(d):
            return fields.Datetime.to_string(d) if d else ""

        out = []
        for r in recs:
            when = r.received_datetime or r.sent_datetime or r.date
            is_sent = (r.folder == "sent") or (
                (r.sender_address or "").strip().lower() == acc_email
            )
            out.append(
                {
                    "id": r.outlook_msg_id,
                    "subject": r.subject or "No Subject",
                    "sender": r.sender_name
                    or (r.sender_address or "").split("@")[0]
                    or "Unknown Sender",
                    "to": r.to_addresses or "",
                    "receiver": r.to_addresses or "",
                    "cc": r.cc_addresses or "",
                    "bcc": r.bcc_addresses or "",
                    "date_received": _fmt_dt(when),
                    "body": r.body_html or r.body_text or "",
                    "attachments": [],
                    "thread_id": r.thread_id or thread_id,
                    "message_id": r.internet_message_id or "",
                    "is_read": r.is_read,
                    "is_starred_mail": False,
                    "is_sent_mail": bool(is_sent),
                    "avatar_url": None,
                    "type": "outlook",
                }
            )

        return {"status": "ok", "messages": out}

    def _hydrate_conversation_from_graph(self, conv_id, account):
        access_token = account.outlook_access_token or ""
        refresh_token = account.outlook_refresh_token or ""
        cfg = request.env["outlook.mail.sync"].sudo().get_outlook_config()

        def _headers(tok):
            return {
                "Authorization": f"Bearer {tok}",
                "Prefer": 'outlook.body-content-type="html"',
                "ConsistencyLevel": "eventual",
                "Content-Type": "application/json",
            }

        select_fields = (
            "id,subject,from,sender,toRecipients,ccRecipients,bccRecipients,"
            "sentDateTime,receivedDateTime,body,conversationId,internetMessageId,"
            "isRead,hasAttachments"
        )
        url = (
            "https://graph.microsoft.com/v1.0/me/messages"
            f"?$filter=conversationId eq '{conv_id}'"
            f"&$orderby=receivedDateTime asc"
            f"&$select={select_fields}"
            f"&$top=100"
        )

        def _fetch(tok, u):
            return requests.get(u, headers=_headers(tok))

        r = _fetch(access_token, url)
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
                j = tk.json()
                access_token = j.get("access_token") or access_token
                account.sudo().write(
                    {
                        "outlook_access_token": access_token,
                        "outlook_refresh_token": j.get("refresh_token")
                        or refresh_token,
                    }
                )
                r = _fetch(access_token, url)

        if r.status_code != 200:
            _logger.warning("Graph conversation fetch failed: %s", r.text)
            return

        Message = request.env["outlook.message"].sudo()

        def _consume(resp_json):
            items = resp_json.get("value", []) or []
            for d in items:
                try:
                    Message.upsert_from_graph_detail(
                        d,
                        # folder sẽ được quyết định trong upsert bằng account_email
                        folder_hint="inbox",
                        user_id=request.env.user.id,
                        account_id=account.id,
                        account_email=account.email,  # ✅ RẤT QUAN TRỌNG
                    )
                except Exception:
                    _logger.exception(
                        "Upsert Outlook message (hydrate) failed id=%s", d.get("id")
                    )

        j = r.json()
        _consume(j)
        next_link = j.get("@odata.nextLink")
        while next_link:
            r2 = requests.get(next_link, headers=_headers(access_token))
            if r2.status_code != 200:
                break
            j2 = r2.json()
            _consume(j2)
            next_link = j2.get("@odata.nextLink")

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
