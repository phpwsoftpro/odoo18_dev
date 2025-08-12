/** @odoo-module **/

// --- Helpers cho HTML & inline CID ---
function cleanForwardHtml(html) {
    // bỏ div rỗng và figure bọc table
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

// Chuyển inline attachments (base64) từ state → File và tạo manifest
function buildInlineFilesAndManifest(stateAttachments) {
    const uploadFiles = [];     // [{fileObj, name}]
    const inlineManifest = [];  // [{name, cid, mimetype}]
    (stateAttachments || []).forEach(item => {
        if (item.fileObj) {
            // file người dùng chọn
            uploadFiles.push({ fileObj: item.fileObj, name: item.name || item.fileObj.name });
        } else if (item.content && item.cid && item.mimetype && item.name) {
            // ảnh inline từ forward: content là base64 "thuần"
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
    const cc = document.querySelector('.compose-input.cc')?.value || '';
    const bcc = document.querySelector('.compose-input.bcc')?.value || '';
    const subject = document.querySelector('.compose-input.subject')?.value || '';

    let body = window.editorInstance ? window.editorInstance.getData() : '';
    body = body.replace(/<table/g, '<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse;"');

    // cắt phần quote nếu có
    const splitIndex = body.indexOf('<div class="reply-quote">');
    let cleanBody = splitIndex !== -1 ? body.slice(0, splitIndex) : body;
    cleanBody = cleanForwardHtml(cleanBody);

    const hasAnyRecipient = [to, cc, bcc].some(v => (v || '').trim());
    if (!hasAnyRecipient) { alert("Vui lòng nhập ít nhất một địa chỉ (To, Cc hoặc Bcc)."); return; }

    const account_id = this.state.activeTabId;
    const account = this.state.accounts.find(a => String(a.id) === String(account_id));
    if (!account) {
        alert("Không xác định được tài khoản gửi.");
        return;
    }
    if (!account_id) { alert("Không xác định được tài khoản gửi."); return; }

    const hasAttachment = this.state.attachments && this.state.attachments.length > 0;
    const finalSubject = subject.trim() || (cleanBody.trim() || hasAttachment ? "No Subject" : "");
    const finalBody = (cleanBody.trim() || hasAttachment) ? cleanBody.trim() : "";
    const finalSubject = subject.trim() || ((cleanBody.trim() || hasAttachment) ? "No Subject" : "");
    const finalBody = (cleanBody.trim() || (hasAttachment ? "" : null));

    if (!finalSubject && !finalBody && !hasAttachment) {
        alert("Vui lòng nhập nội dung email hoặc đính kèm tệp.");
        return;
    }

    // 🔁 Lấy file từ state: gồm file người dùng + ảnh inline từ forward (base64)
    const { uploadFiles, inlineManifest } = buildInlineFilesAndManifest(this.state.attachments || []);

    // Đổi <img data-cid> → src="cid:..." để backend map đúng với Content-ID
    const bodyToSend = applyCidSrc(finalBody ?? "");

    const formData = new FormData();
    formData.append("to", to);
    if (cc.trim()) formData.append("cc", cc);
    if (bcc.trim()) formData.append("bcc", bcc);
    formData.append("cc", cc);     
    formData.append("bcc", bcc);   
    formData.append("subject", finalSubject);
    formData.append("body_html", finalBody);
    formData.append("account_id", account_id);
    formData.append("account_type", account.type); // 👈 cho backend biết là gmail hay outlook
    formData.append("body_html", bodyToSend ?? "");
    if (thread_id) formData.append("thread_id", thread_id);
    if (message_id) formData.append("message_id", message_id);

    // attachments
    (this.state.attachments || []).forEach((f) => {
        formData.append('attachments[]', f.fileObj, f.name);
    });

    console.log("🚀 FormData:", [...formData.entries()]);
    formData.append("account_id", account_id);
    formData.append("provider", "gmail"); // rõ ràng cho backend

    // ✅ đính kèm tất cả file
    uploadFiles.forEach(f => formData.append('attachments[]', f.fileObj, f.name));

    // 👇 GỬI manifest để server set inline + Content-ID
    if (inlineManifest.length) {
        formData.append("inline_manifest", JSON.stringify(inlineManifest));
    }

    console.log("🖼️ inlineManifest:", inlineManifest);
    console.log("🚀 FormData keys:", [...formData.keys()]);

    // 👇 Chọn endpoint theo loại tài khoản
    const endpoint = account.type === 'gmail'
        ? '/api/send_email'
        : '/outlook/send_email';

    fetch(endpoint, { method: 'POST', body: formData })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success' || data.status === 'ok') {
                alert("✅ Email đã được gửi thành công!");
                this.state.showComposeModal = false;
                this.state.attachments = [];
                if (window.editorInstance) {
                    window.editorInstance.destroy();
                    window.editorInstance = null;
                }
                this.render();
            } else {
                throw new Error(data.message || '❌ Gửi mail thất bại');
            }
        })
        .catch(err => {
            alert("⚠️ Có lỗi khi gửi email, xem console.");
            console.error("❌ Gửi mail lỗi:", err);
        });
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

// ✅ Gắn sự kiện xử lý chọn file
document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("file_attachments");
    const preview = document.getElementById("attachment_preview");

    if (!input || !preview) return;

    input.addEventListener("change", (e) => {
        const files = Array.from(e.target.files);
        preview.innerHTML = '';
        attachedFiles = [];

        files.forEach((file) => {
            // ✅ Ghi rõ tên để không bị mất tên file tiếng Việt
            attachedFiles.push({
                fileObj: file,
                name: file.name,
            });

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

        // Lưu vào state của component
        this.state.attachments = attachedFiles;
        input.value = '';
    });
});
