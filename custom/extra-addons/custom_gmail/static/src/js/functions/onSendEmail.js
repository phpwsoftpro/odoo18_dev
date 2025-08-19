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

// Quét ảnh trong editor thành inline CID
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

        // 1) data:image/*
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

        // 2) blob:*
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

        // 3) /web/content/*
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
    const uploadFiles = [];
    const inlineManifest = [];
    (stateAttachments || []).forEach(item => {
        if (item.fileObj) {
            const name = item.name || item.fileObj.name;
            uploadFiles.push({ fileObj: item.fileObj, name });
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

export function onSendEmail() {
    const composeData = this.state.composeData || {};
    const thread_id = composeData.thread_id || null;
    const message_id = composeData.message_id || null;
 
    const to = document.querySelector('.compose-input.to')?.value || '';
    const cc = document.querySelector('.compose-input.cc')?.value || '';
    const bcc = document.querySelector('.compose-input.bcc')?.value || '';
    const subject = document.querySelector('.compose-input.subject')?.value || '';
 
    let body = window.editorInstance ? window.editorInstance.getData() : '';
    body = body.replace(/<table/g, '<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse;"');
    const splitIndex = body.indexOf('<div class="reply-quote">');
    const cleanBody = splitIndex !== -1 ? body.slice(0, splitIndex) : body;
 
    if (!to.trim()) {
        alert("Vui lòng nhập địa chỉ email.");
        return;
    }
 
    const account_id = this.state.activeTabId;
    const account = this.state.accounts.find(a => String(a.id) === String(account_id));
    if (!account) {
        alert("Không xác định được tài khoản gửi.");
        return;
    }
 
    const hasAttachment = this.state.attachments && this.state.attachments.length > 0;
    const finalSubject = subject.trim() || (cleanBody.trim() || hasAttachment ? "No Subject" : "");
    const finalBody = (cleanBody.trim() || hasAttachment) ? cleanBody.trim() : "";
 
    if (!finalSubject && !finalBody && !hasAttachment) {
        alert("Vui lòng nhập nội dung email hoặc đính kèm tệp.");
        return;
    }
 
    const formData = new FormData();
    formData.append("to", to);
    if (cc.trim()) formData.append("cc", cc);
    if (bcc.trim()) formData.append("bcc", bcc);
    formData.append("subject", finalSubject);
    formData.append("body_html", finalBody);
    formData.append("account_id", account_id);
    formData.append("account_type", account.type); // 👈 cho backend biết là gmail hay outlook
    if (thread_id) formData.append("thread_id", thread_id);
    if (message_id) formData.append("message_id", message_id);
 
    // attachments
    (this.state.attachments || []).forEach((f) => {
        formData.append('attachments[]', f.fileObj, f.name);
    });
 
    console.log("🚀 FormData:", [...formData.entries()]);
 
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
 
        this.state.attachments = attachedFiles;  // ✅ đảm bảo lưu đúng vào state
        input.value = '';
    });
});