/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";

export async function onReplyAll(ev, msg) {
  ev?.stopPropagation?.();
  if (!msg) return;

  // ===== Helpers =====
  const extractEmail = (addr = "") => {
    const m = String(addr).match(/<([^>]+)>/);
    return (m ? m[1] : addr).trim();
  };

  // Chuẩn hoá email (xử lý gmail: bỏ dấu chấm & phần +tag; googlemail -> gmail)
  const normalizeEmail = (e = "") => {
    e = String(e || "").trim().toLowerCase();
    if (!e) return "";
    const [localRaw, domainRaw] = e.split("@");
    if (!domainRaw) return e;
    const domain = domainRaw.replace("googlemail.com", "gmail.com");
    const local = domain === "gmail.com"
      ? (localRaw || "").split("+")[0].replace(/\./g, "")
      : (localRaw || "");
    return `${local}@${domain}`;
  };

  const parseList = (str = "") =>
    String(str)
      .split(/[,;]+/)
      .map((s) => normalizeEmail(extractEmail(s)))
      .filter(Boolean);

  const uniq = (arr) => Array.from(new Set(arr)).filter(Boolean);

  const extractName = (addr = "") => {
    const m = String(addr).match(/^\s*"?([^"<]*?)"?\s*<[^>]+>/);
    const name = (m ? m[1] : String(addr)).trim();
    return /@/.test(name) ? name : (name || "Unknown");
  };

  // ===== Me + aliases (robust) =====
  // đảm bảo luôn có email đăng nhập hiện tại
  if (!this.state.gmail_email && !this.state.outlook_email) {
    const account = this.state.accounts?.find(a => a.id === this.state.activeTabId);
    if (account?.type === "gmail") {
      await this.loadAuthenticatedEmail();
    } else if (account?.type === "outlook") {
      await this.loadOutlookAuthenticatedEmail();
    }
  }

  const activeAcc = this.state.accounts?.find(a => a.id === this.state.activeTabId) || {};
  const maybeSelfCandidates = [
    this.state.gmail_email,
    this.state.outlook_email,
    activeAcc.email,
    activeAcc.login,
    activeAcc.username,
    extractEmail(activeAcc.display_name || ""),
  ].filter(Boolean);

  const aliasNorms = (this.state.account_aliases || []).map(normalizeEmail);
  const selfSet = new Set(
    [
      ...maybeSelfCandidates.map(normalizeEmail),
      ...aliasNorms,
    ].filter(Boolean)
  );
  const isMe = (e) => {
    const n = normalizeEmail(e);
    return n && selfSet.has(n);
  };

  // ===== Tăng độ giàu header nếu cần =====
  let source = msg;
  try {
    const needHeaders =
      !source?.message_id ||
      (!source?.cc && !source?.email_cc) ||
      (!source?.to && !source?.email_receiver) ||
      (!source?.sender && !source?.email_sender) ||
      (!source?.body_cleaned && !(typeof source?.body === "string" && source.body?.trim())) ||
      (!source?.bcc && !source?.email_bcc);

    if (source.thread_id && needHeaders) {
      const accId = parseInt(this.state.activeTabId);
      const res = await rpc("/gmail/thread_detail", { thread_id: source.thread_id, account_id: accId });
      if (res?.status === "ok" && Array.isArray(res.messages) && res.messages.length) {
        const found = res.messages.find(m => m.id === source.id) || res.messages.at(-1);
        source = { ...source, ...found };
      }
    }
  } catch {}

  // ===== Raw headers =====
  const rawFrom = source.from || source.email_sender || source.sender || "";
  const fromEmail = normalizeEmail(extractEmail(rawFrom));
  const rawTo  = source.to  || source.email_receiver || "";
  const rawCc  = source.cc  || source.email_cc       || "";
  const rawBcc = source.bcc || source.email_bcc      || "";
  const replyToList = parseList(source.reply_to || "");

  // Nếu from của message là mình → bổ sung vào selfSet luôn (trường hợp alias chưa load)
  if (fromEmail) selfSet.add(fromEmail);

  // ===== Parse & build recipients =====
  let to = parseList(rawTo);
  let cc = parseList(rawCc);
  // const bcc = parseList(rawBcc); // bcc không hiển thị khi reply

  const sentByMe = isMe(fromEmail);
  const primaryReplyTo = replyToList[0];

  // Nếu KHÔNG phải thư mình gửi → ưu tiên Reply-To/From
  if (!sentByMe) {
    if (primaryReplyTo && !isMe(primaryReplyTo) && !to.includes(primaryReplyTo)) {
      to.unshift(primaryReplyTo);
    } else if (fromEmail && !isMe(fromEmail) && !to.includes(fromEmail)) {
      to.unshift(fromEmail);
    }
  }

  // Loại "tôi" ra khỏi mọi nơi
  const notMe = (e) => e && !isMe(e);
  to = uniq(to).filter(notMe);
  cc = uniq(cc).filter((e) => notMe(e) && !to.includes(e));

  // Fallback: nếu vì lý do nào đó trống hết (thường gặp khi reply-all trên mail mình gửi mà không có ai khác)
  if (!to.length && !cc.length) {
    if (primaryReplyTo && !isMe(primaryReplyTo)) {
      to = [primaryReplyTo];
    } else if (fromEmail && !isMe(fromEmail)) {
      to = [fromEmail];
    }
  }

  // ===== Subject & quoted body =====
  let subject = source.subject || "";
  if (!/^re:/i.test(subject)) subject = `Re: ${subject}`.trim();

  const dateStr  = source.dateDisplayed || source.date_received || "";
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

  // Nếu có CC thì bật ô CC
  this.state.showCc = cc.length > 0;

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
}
