/** @odoo-module **/

// Reuse hàm đã có ở forward
import { extractImagesAsCIDAttachments } from "./onForward";

function extractEmail(raw = "") {
  const s = String(raw).trim();
  const m = s.match(/<([^>]+)>/);
  return (m && m[1]) ? m[1].trim() : s.split(/[;,]/)[0].trim();
}
function escapeHtml(s = "") {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function makeReplySubject(subject = "") {
  const base = String(subject).replace(/^\s*(re|fwd):\s*/gi, "");
  return `Re: ${base}`;
}
function formatReplyHeaderDate(dt) {
  const d = new Date(dt || Date.now());
  return d.toLocaleString("vi-VN", {
    weekday: "short", day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

// đặt caret lên đầu editor (sau khi popup đã khởi tạo CKEditor)
function focusEditorAtTop() {
  // đợi editor khởi tạo xong
  setTimeout(() => {
    const ed = window.editorInstance;
    if (!ed) return;
    ed.editing.view.focus();
    ed.model.change(writer => {
      const root = ed.model.document.getRoot();
      // chọn đầu tiên của node đầu (là <p><br></p> chúng ta chèn)
      const first = root.getChild(0);
      const pos = ed.model.createPositionAt(first, 0);
      writer.setSelection(pos);
    });
  }, 150);
}

// Reply: To + Subject + chèn quote (ảnh xử lý giống forward)
export async function onReply(ev, msg) {
  ev?.preventDefault?.();
  ev?.stopPropagation?.();

  const fromRaw   = msg.from || msg.sender || msg.from_email || msg.email_from || "";
  const fromEmail = extractEmail(fromRaw);

  // 1) Lấy HTML gốc để quote
  const originalBody = msg.body_cleaned || msg.body || "";

  // 2) Convert ảnh /web/content → base64 + gắn CID + tạo attachments inline
  const { html: htmlWithInline, attachments } = await extractImagesAsCIDAttachments(originalBody);

  // 3) Soạn quote giống Gmail
  const when = formatReplyHeaderDate(msg.date_received || msg.date || msg.create_date);
  const header = `
    <p style="margin:0 0 .6em 0;">
      Vào ${escapeHtml(when)} &lt;${escapeHtml(fromEmail)}&gt; đã viết:
    </p>`;

  const quoteBlock = `
    <div class="reply-quote" data-original-mid="${escapeHtml(msg.message_id || "")}">
      ${header}
      <blockquote class="gmail_quote" style="margin:0 0 0 .8ex;border-left:1px solid #ccc;padding-left:1ex">
        ${htmlWithInline}
      </blockquote>
    </div>`;

  // 4) THÊM KHOẢNG TRỐNG Ở TRÊN CHO NGƯỜI DÙNG GÕ
  //    (2 đoạn <p> trống để nhìn giống Gmail, bạn có thể đổi số lượng nếu thích)
  const topSpacer = `<p><br></p><p><br></p>`;

  const bodyHtml = `${topSpacer}${quoteBlock}`;

  // 5) Mở popup – đính kèm inline attachments vừa tạo
  this.openComposeModal("reply", {
    to: fromEmail || "",
    cc: "",
    bcc: "",
    subject: makeReplySubject(msg.subject || ""),
    body: bodyHtml,              // 👈 quote nằm dưới, trống nằm trên
    attachments,                 // ảnh inline từ body gốc
    thread_id: msg.thread_id || null,
    message_id: msg.message_id || null,
    is_reply: true,
  });

  // 6) Đặt caret lên TOP (đoạn trống) để người dùng gõ luôn
  focusEditorAtTop();
}
