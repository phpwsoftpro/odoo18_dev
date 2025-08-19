from odoo import http
from odoo.http import request
import requests
import logging
from lxml import html
import re
import json
import base64

_logger = logging.getLogger(__name__)


class OutlookMessageController(http.Controller):
    @http.route("/outlook/sent_messages", type="json", auth="user", csrf=False)
    def outlook_sent_messages(self, page=1, limit=20):
        account = (
            request.env["outlook.account"]
            .sudo()
            .search([("user_id", "=", request.env.user.id)], limit=1)
        )
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
            }

        try:
            page = int(page or 1)
            limit = max(1, min(int(limit or 20), 50))
        except Exception:
            page, limit = 1, 20

        params = {
            "$orderby": "sentDateTime desc",
            "$top": str(limit),
            "$select": "id,subject,sentDateTime,from,sender,toRecipients,ccRecipients,"
            "bodyPreview,body,conversationId,internetMessageId",
            "$count": "true",
        }
        if page > 1:
            params["$skip"] = str((page - 1) * limit)

        base_url = (
            "https://graph.microsoft.com/v1.0/me/mailFolders('sentitems')/messages"
        )
        resp = requests.get(base_url, headers=_headers(access_token), params=params)

        if resp.status_code == 401 and refresh_token:
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
                new_access = tk.json().get("access_token")
                if new_access:
                    account.sudo().write(
                        {
                            "outlook_access_token": new_access,
                            "outlook_refresh_token": tk.json().get("refresh_token")
                            or refresh_token,
                        }
                    )
                    resp = requests.get(
                        base_url, headers=_headers(new_access), params=params
                    )
            else:
                return {
                    "status": "error",
                    "message": "Outlook token expired. Please log in again.",
                }

        if resp.status_code == 400 and "$skip" in params:
            params.pop("$skip", None)
            resp = requests.get(base_url, headers=_headers(access_token), params=params)

        if resp.status_code != 200:
            _logger.error("❌ Failed to fetch Outlook sent: %s", resp.text)
            return {"status": "error", "message": "Failed to fetch sent messages"}

        data = resp.json()
        items = data.get("value", [])
        total = data.get("@odata.count")

        Message = request.env["outlook.message"].sudo()

        def _addr(obj, key):
            return (obj or {}).get("emailAddress", {}).get(key)

        def _recips(lst):
            out = []
            for r in lst or []:
                ea = (r or {}).get("emailAddress") or {}
                out.append(
                    {"name": ea.get("name") or "", "address": ea.get("address") or ""}
                )
            return out

        def _join(lst):
            parts = []
            for it in lst:
                nm, ad = it.get("name") or "", it.get("address") or ""
                if ad:
                    parts.append(f"{nm} <{ad}>" if nm else ad)
            return ", ".join(parts)

        messages = []
        for m in items:
            try:
                Message.upsert_from_graph_detail(
                    m,
                    folder_hint="sent",
                    user_id=request.env.user.id,
                    account_id=account.id,
                )
            except Exception:
                _logger.exception("Upsert Outlook sent failed for id=%s", m.get("id"))

            to_list = _recips(m.get("toRecipients"))
            cc_list = _recips(m.get("ccRecipients"))
            body_html = (m.get("body") or {}).get("content") or ""

            messages.append(
                {
                    "id": m["id"],
                    "message_id": m.get("internetMessageId"),
                    "thread_id": m.get("conversationId"),
                    "subject": m.get("subject") or "No Subject",
                    "from_name": _addr(m.get("from"), "name"),
                    "from": _addr(m.get("from"), "address"),
                    "sender": _addr(m.get("sender"), "name"),
                    "to": to_list,
                    "cc": cc_list,
                    "email_receiver": _join(to_list),
                    "email_cc": _join(cc_list),
                    "sentDateTime": m.get("sentDateTime"),
                    "date": m.get("sentDateTime"),
                    "bodyPreview": m.get("bodyPreview", ""),
                    "body_html": body_html,
                    "type": "outlook",
                }
            )

        return {
            "status": "ok",
            "messages": messages,
            "total": total if isinstance(total, int) else len(messages),
            "page": page,
            "limit": limit,
        }

    # Đặt bên trong class OutlookMessageController
    @http.route("/outlook/messages_cached", type="json", auth="user", csrf=False)
    def outlook_messages_cached(
        self, folder="inbox", page=1, limit=20, account_id=None
    ):
        try:
            page = max(1, int(page or 1))
            limit = max(1, min(int(limit or 20), 50))
        except Exception:
            page, limit = 1, 20
        offset = (page - 1) * limit

        Message = request.env["outlook.message"].sudo()
        domain = [("user_id", "=", request.env.user.id)]
        if folder in ("inbox", "sent"):
            domain.append(("folder", "=", folder))
        if account_id:
            try:
                domain.append(("account_id", "=", int(account_id)))
            except Exception:
                pass

        total = Message.search_count(domain)
        recs = Message.search(
            domain, order="date desc, id desc", offset=offset, limit=limit
        )

        # Parse "Name <addr>, Name <addr>" -> [{name,address},...]
        def _parse_csv(s):
            out = []
            if not s:
                return out
            for item in [x.strip() for x in s.split(",") if x and x.strip()]:
                m = re.match(r'"?(.*?)"?\s*<([^>]+)>', item)
                if m:
                    name, addr = (m.group(1) or "").strip(), (m.group(2) or "").strip()
                else:
                    name, addr = "", item
                out.append({"name": name, "address": addr})
            return out

        messages = []
        for r in recs:
            # r là bản ghi Odoo (outlook.message)
            to_list = _parse_csv(r.to_addresses)
            cc_list = _parse_csv(r.cc_addresses)

            messages.append(
                {
                    "id": r.outlook_msg_id,
                    "message_id": r.internet_message_id,
                    "thread_id": r.thread_id,
                    "subject": r.subject or "No Subject",
                    "from_name": r.sender_name,
                    "from": r.sender_address,
                    "sender": r.sender_name,  # để FE dùng chung
                    "to": to_list,
                    "cc": cc_list,
                    "email_receiver": r.to_addresses or "",
                    "email_cc": r.cc_addresses or "",
                    "date": r.sent_datetime or r.received_datetime or r.date,
                    "folder": r.folder,
                    "bodyPreview": r.body_preview or "",
                    "body_html": r.body_html or "",
                    "content_type": r.content_type or "html",
                    "type": "outlook",
                }
            )

        return {
            "status": "ok",
            "messages": messages,
            "total": total,
            "page": page,
            "limit": limit,
        }
