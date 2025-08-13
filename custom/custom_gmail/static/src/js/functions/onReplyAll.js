/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

export async function onReplyAll(ev, msg) {
    ev?.stopPropagation?.();
    if (!msg) return;

    console.log("🟢 [ReplyAll] Clicked message:", msg);

    const extractEmail = (addr = "") => {
        const m = String(addr).match(/<([^>]+)>/);
        return (m ? m[1] : addr).trim();
    };
    const extractName = (addr = "") => {
        const m = String(addr).match(/^\s*"?([^"<]*?)"?\s*<[^>]+>/);
        const name = (m ? m[1] : String(addr)).trim();
        return /@/.test(name) ? name : (name || "Unknown");
    };
    const parseList = (str = "") =>
        String(str)
            .split(/[,;]+/)
            .map((s) => extractEmail(s).toLowerCase())
            .map((s) => s.trim())
            .filter(Boolean);
    const uniq = (arr) => Array.from(new Set(arr)).filter(Boolean);

    // Lấy email của mình
    if (!this.state.gmail_email && !this.state.outlook_email) {
        const account = this.state.accounts?.find(a => a.id === this.state.activeTabId);
        if (account?.type === "gmail") await this.loadAuthenticatedEmail();
        else if (account?.type === "outlook") await this.loadOutlookAuthenticatedEmail();
    }
    const me = (this.state.gmail_email || this.state.outlook_email || "").toLowerCase();
    const myAliases = (this.state.account_aliases || []).map(a => a.toLowerCase());
    const isMe = (email) => {
        const e = (email || "").toLowerCase();
        return e === me || myAliases.includes(e);
    };

    // Bổ sung log kiểm tra email đăng nhập
    console.log("📧 My Email:", me, "Aliases:", myAliases);

    // Lấy message đầy đủ
    let source = msg;
    try {
        const needHeaders =
            !source?.message_id ||
            (!source?.cc && !source?.email_cc) ||
            (!source?.to && !source?.email_receiver) ||
            (!source?.sender && !source?.email_sender) ||
            (!source?.body_cleaned && !(typeof source?.body === "string" && source.body.trim()));

        if (source.thread_id && needHeaders) {
            console.log("🔍 Fetching thread detail for:", source.thread_id);
            const accId = parseInt(this.state.activeTabId);
            const res = await rpc("/gmail/thread_detail", {
                thread_id: source.thread_id,
                account_id: accId,
            });
            if (res?.status === "ok" && Array.isArray(res.messages) && res.messages.length) {
                const found = res.messages.find(m => m.id === source.id) || res.messages[res.messages.length - 1];
                source = { ...source, ...found };
                console.log("✅ Updated source from thread_detail:", source);
            } else {
                console.warn("⚠️ No messages found in thread_detail");
            }
        }
    } catch (e) {
        console.warn("❌ reply-all: fetch thread_detail failed", e);
    }

    // Build danh sách To / CC
    const rawFrom = source.from || source.email_sender || source.sender || "";
    const fromEmail = extractEmail(rawFrom).toLowerCase();

    let to = parseList(source.to || source.email_receiver || "");
    let cc = parseList(source.cc || source.email_cc || "");

    console.log("📌 Before filtering - TO:", to, "CC:", cc, "FROM:", fromEmail);

    // Ưu tiên reply-to
    const replyToList = parseList(source.reply_to || "");
    const primaryReplyTo = replyToList[0];
    if (primaryReplyTo) {
        if (!isMe(primaryReplyTo) && !to.includes(primaryReplyTo)) {
            to.unshift(primaryReplyTo);
        }
    } else {
        if (fromEmail && !isMe(fromEmail) && !to.includes(fromEmail)) {
            to.unshift(fromEmail);
        }
    }

    const notMe = (e) => e && !isMe(e);
    to = uniq(to).filter(notMe);
    cc = uniq(cc).filter((e) => notMe(e) && !to.includes(e));

    console.log("📌 After filtering - TO:", to, "CC:", cc);

    // Subject
    let subject = source.subject || "";
    if (!/^re:/i.test(subject)) subject = `Re: ${subject || ""}`.trim();

    // Quoted body
    const dateStr = source.dateDisplayed || source.date_received || "";
    const fromName = extractName(source.sender || source.email_sender || rawFrom);
    const bodyHtml = source.body_cleaned || source.body || "";
    const quotedBody = `
        <p></p>
        <div style="border-left:3px solid #ddd;padding-left:12px;margin-top:8px;">
            <div style="color:#555;font-size:12px;margin-bottom:6px;">
                On ${dateStr}, <b>${fromName}</b> wrote:
            </div>
            ${bodyHtml}
        </div>
    `;

    console.log("📝 Final Subject:", subject);
    console.log("📝 Quoted Body:", quotedBody);

    // Gọi modal compose
    this.openComposeModal("replyAll", {
        to: to.join(", "),
        cc: cc.join(", "),
        bcc: "",
        subject,
        body: quotedBody,
        attachments: [],
        thread_id: source.thread_id || null,
        message_id: source.message_id || null,
        is_reply: true,
    });

    console.log("🚀 openComposeModal called with:", {
        to: to.join(", "),
        cc: cc.join(", "),
        subject,
        thread_id: source.thread_id,
        message_id: source.message_id
    });
}
