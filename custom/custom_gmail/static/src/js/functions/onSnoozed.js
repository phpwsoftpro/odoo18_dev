/** @odoo-module **/

export async function onSnoozed() {
    console.log("⏰ Snoozing selected emails...");
    const selectedMessages = this.state.messages.filter(msg => msg.selected);

    if (selectedMessages.length === 0) {
        console.warn("🚫 No emails selected to snooze.");
        return;
    }

    // Cho demo: Chỉ remove khỏi danh sách inbox
    this.state.messages = this.state.messages.filter(msg => !msg.selected);

    // Thêm vào snoozedMessages
    if (!this.state.snoozedMessages) {
        this.state.snoozedMessages = [];
    }
    this.state.snoozedMessages.push(...selectedMessages);

    console.log(`✅ Snoozed ${selectedMessages.length} emails.`);

    this.render();
}
