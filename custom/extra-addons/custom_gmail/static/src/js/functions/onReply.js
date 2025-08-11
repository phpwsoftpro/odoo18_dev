/** @odoo-module **/


export function onReply(ev, selectedMessage) {
    ev.stopPropagation();

    if (!selectedMessage || !selectedMessage.thread_id) {
        console.warn("❌ selectedMessage hoặc thread_id không hợp lệ:", selectedMessage);
        return;
    }

    this.openComposeModal("reply", {
        ...selectedMessage,
        thread_id: selectedMessage.thread_id,
        message_id: selectedMessage.message_id,
    });
}
