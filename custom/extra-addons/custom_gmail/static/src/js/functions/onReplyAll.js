/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

export async function onReplyAll(ev, msg) {
    ev?.stopPropagation?.();
    if (!msg) return;

    const extractEmail = (addr = "") => {
        // lấy email trong <> hoặc trả về chuỗi đã trim
        const m = String(addr).match(/<([^>]+)>/);
        return (m ? m[1] : addr).trim();
    };
    const extractName = (addr = "") => {
        // lấy phần tên trước <...> nếu có
        const m = String(addr).match(/^\s*"?([^"<]*?)"?\s*<[^>]+>/);
        const name = (m ? m[1] : String(addr)).trim();
        // nếu name trùng email thì bỏ
        return /@/.test(name) ? name : (name || "Unknown");
    };
    const parseList = (str = "") =>
        String(str)
            .split(/[,;]+/)
            .map((s) => extractEmail(s).toLowerCase())
            .map((s) => s.trim())
            .filter(Boolean);
    const uniq = (arr) => Array.from(new Set(arr)).filter(Boolean);

    // Lấy email đăng nhập (me) + alias (nếu có)
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

    // Lấy đủ thông tin message
    let source = msg;
    try {
        const needHeaders =
            !source?.message_id ||
            (!source?.cc && !source?.email_cc) ||
            (!source?.to && !source?.email_receiver) ||
            (!source?.sender && !source?.email_sender) ||
            (!source?.body_cleaned && !(typeof source?.body === "string" && source.body.trim()));

        if (source.thread_id && needHeaders) {
            const accId = parseInt(this.state.activeTabId);
            const res = await rpc("/gmail/thread_detail", {
                thread_id: source.thread_id,
                account_id: accId,
            });
            if (res?.status === "ok" && Array.isArray(res.messages) && res.messages.length) {
                const found = res.messages.find(m => m.id === source.id) || res.messages[res.messages.length - 1];
                source = {
                    ...source,
                    subject: source.subject || found.subject || "",
                    sender: source.sender || found.sender || found.email_sender,
                    email_sender: source.email_sender || found.email_sender,
                    to: found.to || found.email_receiver || source.to || source.email_receiver || "",
                    cc: found.cc || found.email_cc || source.cc || source.email_cc || "",
                    // NEW: thêm reply_to nếu backend trả về
                    reply_to: source.reply_to || found.reply_to || found["Reply-To"] || "",
                    body_cleaned: source.body_cleaned || found.body || "",
                    body: source.body || found.body || "",
                    message_id: source.message_id || found.message_id || "",
                    thread_id: source.thread_id || found.thread_id || source.thread_id || "",
                    date_received: source.date_received || found.date_received || found.date || source.date || "",
                };
            }
        }
    } catch (e) {
        console.warn("reply-all: fetch thread_detail failed", e);
    }

    // --- Build người nhận ---
    const rawFrom = source.from || source.email_sender || source.sender || "";
    const fromEmail = extractEmail(rawFrom).toLowerCase();

    let to = parseList(source.to || source.email_receiver || "");
    let cc = parseList(source.cc || source.email_cc || "");

    // NEW: Ưu tiên Reply-To nếu có
    const replyToList = parseList(source.reply_to || "");
    const primaryReplyTo = replyToList[0];

    if (primaryReplyTo) {
        // Đảm bảo primaryReplyTo nằm trong TO
        if (!isMe(primaryReplyTo) && !to.includes(primaryReplyTo)) {
            to.unshift(primaryReplyTo);
        }
        // Không cần ép fromEmail vào TO nếu đã có reply-to
    } else {
        // Không có Reply-To → ép fromEmail vào TO (trừ khi là mình)
        if (fromEmail && !isMe(fromEmail) && !to.includes(fromEmail)) {
            to.unshift(fromEmail);
        }
    }

    // Loại mình và alias + loại trùng TO/CC
    const notMe = (e) => e && !isMe(e);
    to = uniq(to).filter(notMe);
    cc = uniq(cc).filter((e) => notMe(e) && !to.includes(e));

    // --- Subject ---
    let subject = source.subject || "";
    if (!/^re:/i.test(subject)) subject = `Re: ${subject || ""}`.trim();

    // --- Quoted body ---
    const dateStr = source.dateDisplayed || source.date_received || "";
    const fromName = extractName(source.sender || source.email_sender || rawFrom);
    const bodyHtml =
        (typeof source.body_cleaned === "string" && source.body_cleaned) ||
        (typeof source.body === "string" && source.body) ||
        "";
    const quotedBody = `
        <p></p>
        <div style="border-left:3px solid #ddd;padding-left:12px;margin-top:8px;">
            <div style="color:#555;font-size:12px;margin-bottom:6px;">
                On ${dateStr}, <b>${fromName}</b> wrote:
            </div>
            ${bodyHtml}
        </div>
    `;

    if (!this.state.showComposeModal) this.onComposeClick();

    const waitEditor = () =>
        new Promise((resolve) => {
            let i = 0;
            const t = setInterval(() => {
                if (window.editorInstance || i > 60) {
                    clearInterval(t);
                    resolve();
                }
                i++;
            }, 50);
        });

    setTimeout(async () => {
        if (cc.length && !this.state.showCc) {
            this.state.showCc = true;
            this.render();
        }
        const toInput = document.querySelector(".compose-input.to");
        const ccInput = document.querySelector(".compose-input.cc");
        const subjectInput = document.querySelector(".compose-input.subject");

        if (toInput) toInput.value = to.join(", ");
        if (ccInput) ccInput.value = cc.join(", ");
        if (subjectInput) subjectInput.value = subject;

        await waitEditor();
        if (window.editorInstance) {
            window.editorInstance.setData(quotedBody);
        }
    }, 0);

    this.state.replyContext = {
        mode: "reply_all",
        thread_id: source.thread_id || null,
        message_id: source.message_id || null,
    };
}
