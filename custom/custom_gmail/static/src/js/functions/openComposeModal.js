/** @odoo-module **/
import { fillComposeForm } from "./fillComposeForm";

export function openComposeModal(mode, payload = {}) {
    // payload có thể chứa: to, cc, bcc, subject, body, attachments, thread_id, message_id, draft_id...
    if (this.state.showComposeModal) {
        this.state.showComposeModal = false;
        setTimeout(() => openComposeModalInternal.call(this, mode, payload), 50);
    } else {
        openComposeModalInternal.call(this, mode, payload);
    }
}

async function openComposeModalInternal(mode, data = {}) {
    this.state.composeMode = mode;
    this.state.showComposeModal = true;

    // Lưu metadata phục vụ lúc gửi
    this.state.composeData = {
        thread_id: data.thread_id ?? null,
        message_id: data.message_id ?? null,
        original_sender: data.original_sender || "",
        draft_id: data.draft_id ?? null,
        attachments: Array.isArray(data.attachments) ? data.attachments : [],
        isSaving: false,
    };

    const modalTitle = document.querySelector(".compose-modal-header h3");
    if (modalTitle) {
        modalTitle.textContent =
            mode === "forward" ? "Forward" :
            mode === "reply"   ? "Reply"   :
                                 "New Message";
    }

    setTimeout(async () => {
        this.editorInstance = await this.initCKEditor();

        // ✅ Đổ thẳng dữ liệu từ payload vào form
        fillComposeForm({
            to:      data.to      || "",
            cc:      data.cc      || "",
            bcc:     data.bcc     || "",
            subject: data.subject || "",
            body:    data.body    || "",
        }, this.editorInstance);
    }, 100);
}
