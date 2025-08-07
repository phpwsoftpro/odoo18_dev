/** @odoo-module **/
import { fillComposeForm } from "./fillComposeForm";

export function openComposeModal(mode, msg = null) {
    if (!msg) return;

    if (this.state.showComposeModal) {
        this.state.showComposeModal = false;
        setTimeout(() => {
            openComposeModalInternal.call(this, mode, msg);
        }, 50);
    } else {
        openComposeModalInternal.call(this, mode, msg);
    }
}

async function openComposeModalInternal(mode, msg) {
    this.state.composeMode = mode;
    this.state.showComposeModal = true;

    this.state.composeData = {
        thread_id: msg.thread_id || null,
        message_id: msg.message_id || null,
        original_sender: msg.sender || "",
        draft_id: msg.draft_id || null,
        attachments: msg.attachments || [],
        isSaving: false,
    };

    const modalTitle = document.querySelector(".compose-modal-header h3");
    if (modalTitle) {
        modalTitle.textContent = mode === "forward" ? "Forward" : "New Message";
    }

    setTimeout(async () => {
        this.editorInstance = await this.initCKEditor();

        const subject = mode === "forward" ? `Fwd: ${msg.subject}` : msg.subject;

        fillComposeForm({
            to: "",
            cc: "",
            bcc: "",
            subject: subject,
            body: msg.body || "",
        }, this.editorInstance);
    }, 100);
}
