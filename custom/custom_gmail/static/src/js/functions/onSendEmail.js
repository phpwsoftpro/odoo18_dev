/** @odoo-module **/

// --- Helpers cho HTML & inline CID ---
function cleanForwardHtml(html) {
    html = (html || "").replace(/<div>(?:\s|&nbsp;)*<\/div>/gi, "");
    html = html.replace(/<figure[^>]*>\s*(<table[\s\S]*?<\/table>)\s*<\/figure>/gi, "$1");
    return html;
}

// Đổi mọi <img data-cid="..."> thành src="cid:..."
function applyCidSrc(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html || "", "text/html");
    doc.querySelectorAll("img[data-cid]").forEach(img => {
        const cid = img.getAttribute("data-cid");
        if (cid) img.setAttribute("src", `cid:${cid}`);
    });
    return doc.body ? doc.body.innerHTML : (html || "");
}
// onSendEmail.js
async function harvestInlineDataImages(html) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(html || "", "text/html");
  const extraInline = [];
  let seq = 0;
  const now = Date.now();
  const jobs = [];

  doc.querySelectorAll("img").forEach((img) => {
    if (img.hasAttribute("data-cid")) return;
    const src = img.getAttribute("src") || "";

    // 1) data:image/*  (giữ logic cũ)
    if (src.startsWith("data:image/")) {
      const m = src.match(/^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/);
      if (!m) return;
      const mimetype = m[1];
      const base64 = m[2];
      const ext = (mimetype.split("/")[1] || "png").toLowerCase();
      const name = `inline-${now}-${seq}.${ext}`;
      const cid  = `inline${now}-${seq}@compose.local`;
      seq++;
      img.setAttribute("data-cid", cid);
      extraInline.push({ name, content: base64, mimetype, cid, inline: true });
      return;
    }

    // 2) blob:*  (giữ logic cũ)
    if (src.startsWith("blob:")) {
      jobs.push((async () => {
        try {
          const resp = await fetch(src);
          const blob = await resp.blob();
          const mimetype = blob.type || "image/png";
          const ext = (mimetype.split("/")[1] || "png").toLowerCase();
          const name = `inline-${now}-${seq}.${ext}`;
          const cid  = `inline${now}-${seq}@compose.local`;
          seq++;
          img.setAttribute("data-cid", cid);
          const fileObj = new File([blob], name, { type: mimetype });
          extraInline.push({ fileObj, name, mimetype, cid, inline: true });
        } catch (e) {
          console.warn("⚠️ Không đọc được blob image:", e);
        }
      })());
      return;
    }

    // ✅ 3) /web/content/*  (MỚI: như luồng Forward)
    if (src.startsWith("/web/content/")) {
      jobs.push((async () => {
        try {
          const resp = await fetch(src);
          const blob = await resp.blob();
          const mimetype = blob.type || "image/png";
          const ext = (mimetype.split("/")[1] || "png").toLowerCase();
          const name = `inline-${now}-${seq}.${ext}`;
          const cid  = `inline${now}-${seq}@compose.local`;
          seq++;
          // tạo base64 để vừa hiển thị trong editor, vừa gửi lên server
          const buf = await blob.arrayBuffer();
          const base64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
          img.setAttribute("data-cid", cid);
          img.setAttribute("src", `data:${mimetype};base64,${base64}`);
          extraInline.push({ name, content: base64, mimetype, cid, inline: true });
        } catch (e) {
          console.warn("⚠️ Không đọc được ảnh /web/content:", e);
        }
      })());
    }
  });

  if (jobs.length) await Promise.all(jobs);

  return {
    html: doc.body ? doc.body.innerHTML : (html || ""),
    extraInline,
  };
}


function buildInlineFilesAndManifest(stateAttachments) {
    const uploadFiles = [];     // [{fileObj, name}]
    const inlineManifest = [];  // [{name, cid, mimetype}]
    (stateAttachments || []).forEach(item => {
        if (item.fileObj) {
            const name = item.name || item.fileObj.name;
            uploadFiles.push({ fileObj: item.fileObj, name });
            // ⬅️ MỚI: nếu là inline (có cid) thì thêm vào manifest
            if (item.inline && item.cid) {
                inlineManifest.push({
                    name,
                    cid: item.cid,
                    mimetype: item.fileObj.type || item.mimetype || "image/png",
                });
            }
        } else if (item.content && item.cid && item.mimetype && item.name) {
            const bin = Uint8Array.from(atob(item.content), c => c.charCodeAt(0));
            const fileObj = new File([bin], item.name, { type: item.mimetype });
            uploadFiles.push({ fileObj, name: item.name });
            inlineManifest.push({ name: item.name, cid: item.cid, mimetype: item.mimetype });
        }
    });
    return { uploadFiles, inlineManifest };
}


let attachedFiles = [];

export async function onSendEmail() {
  const composeData = this.state.composeData || {};
  const thread_id = composeData.thread_id || null;
  const message_id = composeData.message_id || null;

  const to = document.querySelector('.compose-input.to')?.value?.trim() || '';
  const cc = document.querySelector('.compose-input.cc')?.value?.trim() || '';
  const bcc = document.querySelector('.compose-input.bcc')?.value?.trim() || '';
  const subject = document.querySelector('.compose-input.subject')?.value || '';
  let body = window.editorInstance ? window.editorInstance.getData() : '';

  // Cắt phần quote nếu có + dọn HTML
  const splitIndex = body.indexOf('<div class="reply-quote">');
  let cleanBody = splitIndex !== -1 ? body.slice(0, splitIndex) : body;
  cleanBody = cleanForwardHtml(cleanBody);

  const hasAnyRecipient = [to, cc, bcc].some(v => (v || '').trim());
  if (!hasAnyRecipient) { alert("Vui lòng nhập ít nhất một địa chỉ (To, Cc hoặc Bcc)."); return; }

  const account_id = this.state.activeTabId;
  if (!account_id) { alert("Không xác định được tài khoản gửi."); return; }

  // Quét ảnh trong editor -> inline (data:, blob:, /web/content/)
  const { html: withDataCid, extraInline } = await harvestInlineDataImages(cleanBody);

  // Đổi <img data-cid> → src="cid:...”
  const bodyToSend = applyCidSrc(withDataCid);

  // Gộp attachments hiện có với ảnh inline mới harvest
  const combinedAttachments = [ ...(this.state.attachments || []), ...extraInline ];

  const hasAttachment = combinedAttachments.length > 0;
  const finalSubject = subject.trim() || ((bodyToSend.trim() || hasAttachment) ? "No Subject" : "");
  const finalBody = (bodyToSend.trim() || (hasAttachment ? "" : null));

  if (!finalSubject && !finalBody && !hasAttachment) {
    alert("Vui lòng nhập nội dung email hoặc đính kèm tệp.");
    return;
  }

  // Tạo files upload + inline_manifest
  const { uploadFiles, inlineManifest } = buildInlineFilesAndManifest(combinedAttachments);

  // FormData
  const formData = new FormData();
  formData.append("to", to);
  formData.append("cc", cc);
  formData.append("bcc", bcc);
  formData.append("subject", finalSubject);
  formData.append("body_html", finalBody ?? "");
  if (thread_id)  formData.append("thread_id", thread_id);
  if (message_id) formData.append("message_id", message_id);
  formData.append("account_id", account_id);
  formData.append("provider", "gmail");
  uploadFiles.forEach(f => formData.append('attachments[]', f.fileObj, f.name));
  if (inlineManifest.length) formData.append("inline_manifest", JSON.stringify(inlineManifest));

  // Gửi
  try {
    const response = await fetch('/api/send_email', { method: 'POST', body: formData });
    const data = await response.json();
    if (data.status === 'success') {
      alert("✅ Email đã được gửi thành công!");
      this.state.showComposeModal = false;
      this.state.attachments = [];
      if (window.editorInstance) { window.editorInstance.destroy(); window.editorInstance = null; }
      this.render();
    } else {
      throw new Error(data.message || 'Gửi mail thất bại');
    }
  } catch (err) {
    alert("⚠️ Có lỗi khi gửi email.");
  }
}
