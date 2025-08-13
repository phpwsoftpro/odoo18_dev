/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

export async function onReplyAll(ev, msg) {
    ev?.stopPropagation?.();
    if (!msg) return;


    const extractEmail = (addr = "") => {
        const m = String(addr).match(/<(.+?)>/);
        return (m ? m[1] : addr).trim();
    };
    const parseList = (str = "") =>
        String(str)
            .split(/[,;]+/)
            .map((s) => extractEmail(s).toLowerCase())
            .filter(Boolean);
    const uniq = (arr) => Array.from(new Set(arr)).filter(Boolean);

    // đảm bảo có đủ header/body trước khi build quoted
    let source = msg;
    try {
        const needHeaders =
            (!source?.cc && !source?.email_cc) ||
            (!source?.to && !source?.email_receiver) ||
            (!source?.sender && !source?.email_sender) ||
            (!source?.body_cleaned &&
                !(typeof source?.body === "string" && source.body.trim()));

        if (source.thread_id && needHeaders) {
            const accId = parseInt(this.state.activeTabId);
            const res = await rpc("/gmail/thread_detail", {
                thread_id: source.thread_id,
                account_id: accId,
            });
            if (res?.status === "ok" && Array.isArray(res.messages)) {
                const found =
                    res.messages.find((m) => m.id === source.id) ||
                    res.messages[res.messages.length - 1];

                if (found) {
                    source = {
                        ...source,
                        body_cleaned: found.body || found.body_cleaned || "",
                        subject: source.subject || found.subject,
                        sender:
                            source.sender || found.sender || found.email_sender,
                        email_sender:
                            source.email_sender || found.email_sender,
                        to:
                            source.to ||
                            found.to ||
                            found.email_receiver ||
                            "",
                        cc:
                            source.cc ||
                            found.cc ||
                            found.email_cc ||
                            "",
                        date_received:
                            source.date_received ||
                            found.date_received ||
                            found.date ||
                            "",
                        dateDisplayed: source.dateDisplayed,
                    };
                }
            }
        }
    } catch (e) {
        console.warn("reply-all: fetch thread_detail failed", e);
    }

    // build To / Cc
    const me = (this.state.gmail_email || this.state.outlook_email || "")
        .toLowerCase();
    const fromEmail = extractEmail(
        source.from || source.email_sender || source.sender || ""
    ).toLowerCase();

    let to = parseList(source.to || source.email_receiver || "");
    let cc = parseList(source.cc || source.email_cc || "");

    if (fromEmail && !to.includes(fromEmail) && fromEmail !== me) {
        to.unshift(fromEmail);
    }

    to = uniq(to).filter((e) => e !== me);
    cc = uniq(cc).filter((e) => e !== me && !to.includes(e));

    // subject
    let subject = source.subject || "";
    if (!/^re:/i.test(subject)) subject = `Re: ${subject}`;

    // quoted body
    const dateStr = source.dateDisplayed || source.date_received || "";
    const fromName = source.sender || source.email_sender || "Unknown";
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

    // mở compose nếu chưa mở
    if (!this.state.showComposeModal) this.onComposeClick();

    // chờ CKEditor sẵn sàng
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

    // lưu context để gửi đúng thread (dùng RFC Message-Id)
    this.state.replyContext = {
        mode: "reply_all",
        thread_id: source.thread_id || null,
        message_id: source.message_id || null,
    };
    }