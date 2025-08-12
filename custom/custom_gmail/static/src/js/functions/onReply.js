/** @odoo-module **/

// Lấy email từ "Tên <a@b.com>" hoặc chỉ "a@b.com"
function extractEmail(raw = "") {
  const s = String(raw).trim();
  const m = s.match(/<([^>]+)>/);
  return (m && m[1]) ? m[1].trim() : s.split(/[;,]/)[0].trim();
}

// Subject dạng Reply
function makeReplySubject(subject = "") {
  const base = String(subject).replace(/^\s*(re|fwd):\s*/gi, "");
  return `Re: ${base}`;
}

// ==== REPLY: chỉ To + Subject, body rỗng ====
export function onReply(ev, msg) {
  ev?.preventDefault?.();
  ev?.stopPropagation?.();

  const fromRaw   = msg.from || msg.sender || msg.from_email || msg.email_from || "";
  const fromEmail = extractEmail(fromRaw);

  this.openComposeModal("reply", {
    to: fromEmail || "",
    cc: "",
    bcc: "",
    subject: makeReplySubject(msg.subject || ""),
    body: "",                     // ✅ không chèn nội dung gốc
    attachments: [],              // ✅ không kéo theo file/ảnh
    thread_id: msg.thread_id || null,
    message_id: msg.message_id || null,
    is_reply: true,
  });
}
