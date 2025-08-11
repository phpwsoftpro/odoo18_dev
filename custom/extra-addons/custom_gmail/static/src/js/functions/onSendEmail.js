/** @odoo-module **/

let attachedFiles = [];

export function onSendEmail() {
    const composeData = this.state.composeData || {};
    const thread_id = composeData.thread_id || null;
    const message_id = composeData.message_id || null;

    const to = document.querySelector('.compose-input.to')?.value || '';
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
    if (!account_id) {
        alert("Không xác định được tài khoản gửi.");
        return;
    }

    const trimmedSubject = subject.trim();
    const trimmedBody = cleanBody.trim();
    const hasBody = !!trimmedBody;
    const hasAttachment = this.state.attachments && this.state.attachments.length > 0;

    const finalSubject = trimmedSubject || (hasBody || hasAttachment ? "No Subject" : "");
    const finalBody = hasBody ? trimmedBody : (hasAttachment ? "" : null);

    if (!finalSubject && !finalBody && !hasAttachment) {
        alert("Vui lòng nhập nội dung email hoặc đính kèm tệp.");
        return;
    }

    const formData = new FormData();
    formData.append("to", to);
    formData.append("subject", finalSubject);
    formData.append("body_html", finalBody ?? "");
    if (thread_id) formData.append("thread_id", thread_id);
    if (message_id) formData.append("message_id", message_id);
    formData.append("account_id", account_id);

    // ✅ Thêm file đính kèm
    this.state.attachments.forEach((f) => {
        formData.append('attachments[]', f.fileObj, f.name);
    });

    console.log("🚀 FormData:", [...formData.entries()]);

    fetch('/api/send_email', {
        method: 'POST',
        body: formData,
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
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
