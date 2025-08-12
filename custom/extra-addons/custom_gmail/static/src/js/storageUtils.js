/** @odoo-module **/
export async function saveStarredState(msg) {
    console.log("💾 Saving star state for msg ID", msg.id, "starred:", msg.is_starred_mail);

    try {
        const response = await fetch("/gmail/set_star", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: {
                    id: msg.id,
                    starred: msg.is_starred_mail,
                },
            }),
        });

        const data = await response.json();
        console.log("✅ DB updated:", data);

        if (data.result?.status !== "ok") {
            console.warn("⚠️ Server response not ok:", data);
        }
    } catch (err) {
        console.error("❌ Failed to update star:", err);
    }
}

export function loadStarredState() {
    const starredEmails = JSON.parse(localStorage.getItem("starredEmails")) || [];
    this.state.messages.forEach(msg => {
        msg.starred = starredEmails.includes(msg.id);
    });
}