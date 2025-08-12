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
//  Quét ảnh base64 trong HTML -> gắn data-cid & sinh danh sách attachments inline
function harvestInlineDataImages(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html || "", "text/html");
    const extraInline = []; // {name, content, mimetype, cid, inline:true}
    let seq = 0;

    doc.querySelectorAll("img").forEach(img => {
        if (img.hasAttribute("data-cid")) return; // đã xử lý (từ forward)
        const src = img.getAttribute("src") || "";
        if (!src.startsWith("data:image/")) return;

        const m = src.match(/^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/);
        if (!m) return;

        const mimetype = m[1];
        const base64 = m[2];
        const ext = (mimetype.split("/")[1] || "png").toLowerCase();
        const name = `inline-${Date.now()}-${seq}.${ext}`;
        const cid = `inline${Date.now()}-${seq}@compose.local`;
        seq++;

        // gắn data-cid để lát nữa applyCidSrc() đổi sang src="cid:..."
        img.setAttribute("data-cid", cid);

        extraInline.push({ name, content: base64, mimetype, cid, inline: true });
    });

    return {
        html: doc.body ? doc.body.innerHTML : (html || ""),
        extraInline,
    };
}

// Chuyển inline attachments (base64) từ state → File và tạo manifest
function buildInlineFilesAndManifest(stateAttachments) {
    const uploadFiles = [];     // [{fileObj, name}]
    const inlineManifest = [];  // [{name, cid, mimetype}]
    (stateAttachments || []).forEach(item => {
        if (item.fileObj) {
            uploadFiles.push({ fileObj: item.fileObj, name: item.name || item.fileObj.name });
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

    // cắt phần quote nếu có + dọn HTML
    const splitIndex = body.indexOf('<div class="reply-quote">');
    let cleanBody = splitIndex !== -1 ? body.slice(0, splitIndex) : body;
    cleanBody = cleanForwardHtml(cleanBody);

    const hasAnyRecipient = [to, cc, bcc].some(v => (v || '').trim());
    if (!hasAnyRecipient) { alert("Vui lòng nhập ít nhất một địa chỉ (To, Cc hoặc Bcc)."); return; }

    const account_id = this.state.activeTabId;
    if (!account_id) { alert("Không xác định được tài khoản gửi."); return; }

    //  NEW: quét ảnh base64 dán trong editor -> tạo inline attachments + gắn data-cid
    const { html: withDataCid, extraInline } = harvestInlineDataImages(cleanBody);

    // Đổi <img data-cid> → src="cid:..." (áp dụng cho cả forward & editor dán ảnh)
    const bodyToSend = applyCidSrc(withDataCid);

    // Gộp attachments hiện có (file người dùng + ảnh forward) với ảnh mới harvest
    const combinedAttachments = [ ...(this.state.attachments || []), ...extraInline ];

    const hasAttachment = combinedAttachments.length > 0;
    const finalSubject = subject.trim() || ((bodyToSend.trim() || hasAttachment) ? "No Subject" : "");
    const finalBody = (bodyToSend.trim() || (hasAttachment ? "" : null));

    if (!finalSubject && !finalBody && !hasAttachment) {
        alert("Vui lòng nhập nội dung email hoặc đính kèm tệp.");
        return;
    }

    //  Tạo file upload & inline_manifest từ combinedAttachments
    const { uploadFiles, inlineManifest } = buildInlineFilesAndManifest(combinedAttachments);

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

    console.log("🖼️ inlineManifest:", inlineManifest);
    console.log("🚀 FormData keys:", [...formData.keys()]);

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
            throw new Error(data.message || '❌ Gửi mail thất bại');
        }
    } catch (err) {
        alert("⚠️ Có lỗi khi gửi email, xem console.");
        console.error("❌ Gửi mail lỗi:", err);
    }
}

// Gắn sự kiện xử lý chọn file 
document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("file_attachments");
    const preview = document.getElementById("attachment_preview");

    if (!input || !preview) return;

    input.addEventListener("change", (e) => {
        const files = Array.from(e.target.files);
        preview.innerHTML = '';
        attachedFiles = [];

        files.forEach((file) => {
            attachedFiles.push({ fileObj: file, name: file.name });

            const li = document.createElement("li");
            li.textContent = `📄 ${file.name}`;
            li.style.marginBottom = "5px";

            const removeBtn = document.createElement("button");
            removeBtn.textContent = "❌";
            removeBtn.style.marginLeft = "10px";
            removeBtn.style.cursor = "pointer";
            removeBtn.onclick = () => {
                attachedFiles = attachedFiles.filter(f => f.fileObj !== file);
                li.remove();
            };

            li.appendChild(removeBtn);
            preview.appendChild(li);
        });

        this.state.attachments = attachedFiles;
        input.value = '';
    });
});
