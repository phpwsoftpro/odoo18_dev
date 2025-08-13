/** @odoo-module **/

function extractEmail(raw = "") {
  const s = String(raw).trim();
  const m = s.match(/<([^>]+)>/);
  return (m && m[1]) ? m[1].trim() : s.split(/[;,]/)[0].trim();
}

function makeReplySubject(subject = "") {
  const base = String(subject).replace(/^\s*(re|fwd):\s*/gi, "");
  return `Re: ${base}`;
}

// Reply: chỉ To + Subject, body trống
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
    body: "",
    attachments: [],
    thread_id: msg.thread_id || null,
    message_id: msg.message_id || null,
    is_reply: true,
  });
}
