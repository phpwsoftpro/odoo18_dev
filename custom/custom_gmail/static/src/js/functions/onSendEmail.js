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
//  Quét ảnh base64/blob trong HTML -> gắn data-cid & sinh danh sách attachments inline
async function harvestInlineDataImages(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html || "", "text/html");
    const extraInline = []; // {name, content|fileObj, mimetype, cid, inline:true}
    let seq = 0;
    const now = Date.now();
    const jobs = [];

    doc.querySelectorAll("img").forEach((img) => {
        if (img.hasAttribute("data-cid")) return; // đã xử lý (từ forward/editor)
        const src = img.getAttribute("src") || "";

        // 1) data:image/*  (giữ nguyên)
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

        // 2) blob:*  (mới thêm)
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

  const to = document.querySelector('.compose-input.to')?.value || '';
  const cc = document.querySelector('.compose-input.cc')?.value || '';
  const bcc = document.querySelector('.compose-input.bcc')?.value || '';
  const subject = document.querySelector('.compose-input.subject')?.value || '';
  let body = window.editorInstance ? window.editorInstance.getData() : '';

  // 🚩 LOG: thông tin đầu vào
  console.groupCollapsed("📨 [SendEmail] initial");
  console.log("mode:", message_id ? "reply" : "new/forward");
  console.log("thread_id:", thread_id, "message_id:", message_id);
  console.log("to/cc/bcc:", { to, cc, bcc });
  console.log("raw subject:", subject);
  console.groupEnd();

  // cắt phần quote nếu có + dọn HTML
  const splitIndex = body.indexOf('<div class="reply-quote">');
  let cleanBody = splitIndex !== -1 ? body.slice(0, splitIndex) : body;
  cleanBody = cleanForwardHtml(cleanBody);

  // 🚩 LOG: kích thước/nội dung sau clean (cắt bớt để tránh ồn log)
  console.groupCollapsed("🧼 body after clean");
  console.log("length:", (cleanBody || "").length);
  console.log("preview:", (cleanBody || "").slice(0, 300));
  console.groupEnd();

  const hasAnyRecipient = [to, cc, bcc].some(v => (v || '').trim());
  if (!hasAnyRecipient) { alert("Vui lòng nhập ít nhất một địa chỉ (To, Cc hoặc Bcc)."); return; }

  const account_id = this.state.activeTabId;
  if (!account_id) { alert("Không xác định được tài khoản gửi."); return; }

  //  NEW: quét ảnh base64 dán trong editor -> tạo inline attachments + gắn data-cid
  const { html: withDataCid, extraInline } = await harvestInlineDataImages(cleanBody);

  // 🚩 LOG: ảnh base64 đã harvest (sẽ thành inline)
  console.groupCollapsed("🖼️ harvested base64 images → inline");
  console.log("count:", extraInline.length);
  // chỉ log tóm tắt để gọn console
  console.table(extraInline.map(x => ({ name: x.name, cid: x.cid, mimetype: x.mimetype, size_b64: (x.content || "").length })));
  console.groupEnd();

  // Đổi <img data-cid> → src="cid:..."
  const bodyToSend = applyCidSrc(withDataCid);

  // 🚩 LOG: liệt kê các CID đã xuất hiện trong HTML sẽ gửi
  const cidRefsInBody = (bodyToSend.match(/src=["']cid:([^"']+)/gi) || [])
    .map(s => s.replace(/^.*cid:/, ''));
  console.log("🔗 CID refs in body:", cidRefsInBody);

  // Gộp attachments hiện có (file người dùng + ảnh forward) với ảnh mới harvest
  const combinedAttachments = [ ...(this.state.attachments || []), ...extraInline ];

  // 🚩 LOG: tổng hợp attachments trước khi chuyển thành File & manifest
  console.groupCollapsed("📎 combinedAttachments (before upload)");
  console.table(combinedAttachments.map(it => ({
    name: it.name || (it.fileObj && it.fileObj.name) || "(no-name)",
    type: it.mimetype || (it.fileObj && it.fileObj.type) || "",
    hasFileObj: !!it.fileObj,
    hasCid: !!it.cid,
    inlineFlag: !!it.inline
  })));
  console.groupEnd();

  const hasAttachment = combinedAttachments.length > 0;
  const finalSubject = subject.trim() || ((bodyToSend.trim() || hasAttachment) ? "No Subject" : "");
  const finalBody = (bodyToSend.trim() || (hasAttachment ? "" : null));

  if (!finalSubject && !finalBody && !hasAttachment) {
    alert("Vui lòng nhập nội dung email hoặc đính kèm tệp.");
    return;
  }

  //  Tạo file upload & inline_manifest từ combinedAttachments
  const { uploadFiles, inlineManifest } = buildInlineFilesAndManifest(combinedAttachments);

  // 🚩 LOG: kết quả build uploadFiles + inlineManifest
  console.groupCollapsed("🧾 buildInlineFilesAndManifest()");
  console.table(uploadFiles.map(f => ({ name: f.name, type: f.fileObj?.type || "", size: f.fileObj?.size || 0 })));
  console.table(inlineManifest);
  console.groupEnd();

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
  if (inlineManifest.length) {
    formData.append("inline_manifest", JSON.stringify(inlineManifest));
  }

  // 🚩 LOG: nội dung form chuẩn bị gửi
  console.groupCollapsed("📤 FormData overview");
  console.log("keys:", [...formData.keys()]);
  console.log("attachments (names):", uploadFiles.map(f => f.name));
  console.log("inlineManifest CIDs:", inlineManifest.map(m => m.cid));
  console.groupEnd();

  try {
    const response = await fetch('/api/send_email', { method: 'POST', body: formData });
    const data = await response.json();
    if (data.status === 'success') {
      console.info("✅ Send OK. inline vs attach summary:", {
        bodyCidRefs: cidRefsInBody,
        inlineNames: inlineManifest.map(m => m.name),
        attachNames: uploadFiles
          .map(f => f.name)
          .filter(n => !inlineManifest.find(m => m.name === n))
      });
      alert("✅ Email đã được gửi thành công!");
      this.state.showComposeModal = false;
      this.state.attachments = [];
      if (window.editorInstance) { window.editorInstance.destroy(); window.editorInstance = null; }
      this.render();
    } else {
      throw new Error(data.message || '❌ Gửi mail thất bại');
    }
  } catch (err) {
    alert("⚠️ Có lỗi khi gửi email, xem console.");
    console.error("❌ Gửi mail lỗi:", err);
  }
}
