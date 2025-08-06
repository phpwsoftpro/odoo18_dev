//** @odoo-module **/
import { rpc } from "@web/core/network/rpc";

function extractNameFromSender(sender) {
    const match = sender?.match(/^"?([^"<]+?)"?\s*<.*?>$/);
    return match ? match[1].trim() : sender;
}

export async function onAnalyze(ev, msg) {
    console.log("📬 Full email message object (msg):", msg);

    const htmlBody = msg?.body || "";
    const subject = msg?.subject || "No Subject";

    const plainTextBody = htmlBody.replace(/<[^>]+>/g, '').trim();

    const sender_raw = msg?.sender || msg?.email_sender || "Unknown Sender";
    const sender_name = extractNameFromSender(sender_raw);

    // ✅ Quan trọng: Đảm bảo có email rõ ràng
    const email_from = msg?.email_sender 
        || (msg?.sender?.match(/<([^>]+)>/)?.[1]) 
        || "unknown@example.com";

    if (!plainTextBody || plainTextBody.length < 10) {
        alert("⚠️ Không có nội dung để phân tích hoặc nội dung quá ngắn.");
        return;
    }

    try {
        const result = await rpc("/analyze_email_proxy", {
            text: plainTextBody,
            subject,
            sender_name,
            email_from,
            html_body: htmlBody,
        }, {
            headers: {
                "X-API-KEY": "my-secret-key"
            }
        });

        if (result.success) {
            alert("✅ GPT đã phân tích xong!");
            console.log("🧠 Phân tích:", result.result);
        } else {
            console.warn("⚠️ Lỗi phân tích:", result.error);
            alert("❌ " + result.error);
        }
    } catch (error) {
        console.error("❌ Lỗi khi gọi proxy:", error);
        alert("❌ Không thể phân tích email.");
    }
}
