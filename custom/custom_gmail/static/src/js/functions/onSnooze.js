/** @odoo-module **/

export async function onSnooze({ option = null, snoozeDate = null, snoozeTime = null } = {}) {
    console.log("⏰ Snoozing selected emails");

    const selectedMessages = this.state.messages.filter(msg => msg.selected);
    if (selectedMessages.length === 0) {
        console.warn("🚫 No emails selected to snooze.");
        return;
    }

    let finalSnoozeDate;
    const now = new Date();

    if (snoozeDate && snoozeTime) {
        // 🚀 Custom snooze với date + time input type="time"
        finalSnoozeDate = new Date(snoozeDate);
        const [hours, minutes] = snoozeTime.split(":").map(Number);
        finalSnoozeDate.setHours(hours, minutes, 0, 0);

        console.log(`🗓 Custom snooze until: ${finalSnoozeDate.toLocaleString()}`);
    } else if (option) {
        // 🚀 Quick snooze preset
        finalSnoozeDate = new Date();
        switch (option) {
            case "today":
                if (now.getHours() >= 18) {
                    finalSnoozeDate.setDate(now.getDate() + 1);
                    finalSnoozeDate.setHours(8, 0, 0, 0);
                } else {
                    finalSnoozeDate.setHours(18, 0, 0, 0);
                }
                break;
            case "tomorrow":
                finalSnoozeDate.setDate(now.getDate() + 1);
                finalSnoozeDate.setHours(8, 0, 0, 0);
                break;
            case "later_week":
                finalSnoozeDate.setDate(now.getDate() + ((4 - now.getDay() + 7) % 7 || 7));
                finalSnoozeDate.setHours(8, 0, 0, 0);
                break;
            case "weekend":
                finalSnoozeDate.setDate(now.getDate() + ((6 - now.getDay() + 7) % 7 || 7));
                finalSnoozeDate.setHours(8, 0, 0, 0);
                break;
            case "next_week":
                finalSnoozeDate.setDate(now.getDate() + ((8 - now.getDay()) % 7 || 7));
                finalSnoozeDate.setHours(8, 0, 0, 0);
                break;
            default:
                finalSnoozeDate.setHours(8, 0, 0, 0);
        }
        console.log(`🗓 Quick snooze (${option}) until: ${finalSnoozeDate.toLocaleString()}`);
    } else {
        console.warn("🚫 No snooze option or date provided.");
        return;
    }

    selectedMessages.forEach(msg => {
        msg.snoozed_until = finalSnoozeDate.toISOString();
    });

    this.state.messages = this.state.messages.filter(msg => !msg.selected);
    if (!this.state.snoozedMessages) {
        this.state.snoozedMessages = [];
    }
    this.state.snoozedMessages.push(...selectedMessages);

    console.log(`✅ Snoozed ${selectedMessages.length} emails.`);

    this.state.showSnoozeMenu = false;
    document.removeEventListener("click", this.boundCloseSnoozeMenu);

    this.render();
}
