/** @odoo-module **/
export async function toggleStar(msg) {
    msg.is_starred_mail = !msg.is_starred_mail;
    await this.saveStarredState(msg);

    const acc = this.state.accounts.find(a => a.id === this.state.activeTabId);
    const activeEmail = acc ? acc.email : "";

    // Update trong list
    this.state.messages = this.state.messages.map(m =>
        m.id === msg.id ? { ...m, is_starred_mail: msg.is_starred_mail } : m
    );

    // Update trong grouped
    if (this.state.messagesByEmail[activeEmail]) {
        this.state.messagesByEmail[activeEmail] = this.state.messagesByEmail[activeEmail].map(m =>
            m.id === msg.id ? { ...m, is_starred_mail: msg.is_starred_mail } : m
        );
    }

    // Update thread
    if (msg.thread_id && this.state.threads[msg.thread_id]) {
        this.state.threads[msg.thread_id] = this.state.threads[msg.thread_id].map(m =>
            m.id === msg.id ? { ...m, is_starred_mail: msg.is_starred_mail } : m
        );
    }

    // Update mail đang mở
    if (this.state.currentThread) {
        this.state.currentThread = this.state.currentThread.map(m =>
            m.id === msg.id ? { ...m, is_starred_mail: msg.is_starred_mail } : m
        );
    }

    if (this.state.selectedMessage?.id === msg.id) {
        this.state.selectedMessage = { ...this.state.selectedMessage, is_starred_mail: msg.is_starred_mail };
    }

    // Nếu ở folder starred, bỏ sao sẽ loại khỏi list ngay
    if (this.state.currentFolder === "starred" && !msg.is_starred_mail) {
        this.state.messages = this.state.messages.filter(m => m.id !== msg.id);

        if (this.state.messagesByEmail[activeEmail]) {
            this.state.messagesByEmail[activeEmail] = this.state.messagesByEmail[activeEmail].filter(m => m.id !== msg.id);
        }
    }

    this.render();
}
