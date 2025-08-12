/** @odoo-module **/
import { fillComposeForm } from "./fillComposeForm";

export function openComposeModal(mode, payload = {}) {
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

  this.state.composeData = {
    thread_id: data.thread_id ?? null,
    message_id: data.message_id ?? null,
    draft_id: data.draft_id ?? null,
    original_sender: data.original_sender || "",
    attachments: Array.isArray(data.attachments) ? data.attachments : [],
    isSaving: false,
  };

  const titleEl = document.querySelector(".compose-modal-header h3");
  if (titleEl) titleEl.textContent = mode === "reply" ? "Reply" : mode === "forward" ? "Forward" : "New Message";

  setTimeout(async () => {
    this.editorInstance = await this.initCKEditor();
    fillComposeForm({
      to:      data.to      || "",
      cc:      data.cc      || "",
      bcc:     data.bcc     || "",
      subject: data.subject || "",
      body:    data.body    || "",
    }, this.editorInstance);
  }, 100);
}
