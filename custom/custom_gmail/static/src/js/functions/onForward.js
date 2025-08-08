/** @odoo-module **/

// ✅ CHUẨN BỊ ẢNH ĐỂ GỬI: chuyển base64 → cid
export function prepareImagesForSending() {
    const composeBodyEl = document.querySelector('.compose-body');
    if (!composeBodyEl) return;

    composeBodyEl.querySelectorAll("img").forEach(img => {
        const cid = img.getAttribute("data-cid");
        if (cid) {
            img.setAttribute("src", `cid:${cid}`);
            console.log(`🔁 Gán lại src = cid:${cid} cho ảnh`, img);
        }
    });
}

// ✅ TRÍCH XUẤT ẢNH GỬI KÈM VÀ THAY THẾ SRC = base64 + data-cid
export async function extractImagesAsCIDAttachments(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");
    const imgs = doc.querySelectorAll("img");

    const attachments = [];

    for (let i = 0; i < imgs.length; i++) {
        const img = imgs[i];
        const src = img.getAttribute("src") || "";

        if (src.startsWith("/web/content/")) {
            try {
                const response = await fetch(src);
                const blob = await response.blob();

                const base64Full = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });

                const mimeMatch = base64Full.match(/^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/);
                if (!mimeMatch) continue;

                const mimetype = mimeMatch[1];
                const base64 = mimeMatch[2];
                const ext = mimetype.split("/")[1] || "png";
                const cid = `inlineimage${i}@forward.local`;
                const filename = `image${i}.${ext}`;

                // Gán src = base64 (hiển thị nội bộ)
                img.setAttribute("src", base64Full);
                img.setAttribute("data-cid", cid);
                img.setAttribute("data-original-src", base64Full);

                // Style an toàn cho Gmail
                const existingStyle = img.getAttribute("style") || "";
                img.setAttribute(
                    "style",
                    `${existingStyle}; max-width:100%; height:auto; display:block; object-fit:contain; border:0;`
                );

                attachments.push({
                    name: filename,
                    content: base64,
                    mimetype,
                    cid,
                    inline: true,
                    originalSrc: base64Full
                });

                console.log(`📎 Đã xử lý ảnh đính kèm: ${filename}`, { cid, mimetype });

            } catch (err) {
                console.warn("⚠️ Không thể xử lý ảnh:", src, err);
            }
        }
    }

    return {
        html: doc.body ? doc.body.innerHTML : html,
        attachments,
    };
}

// ✅ XỬ LÝ GỬI FORWARD
export function onForward(ev, msg) {
    ev.preventDefault();
    ev.stopPropagation();

    const dropdown = document.querySelector(".dropdown-menu.show, .o-mail-message-options-dropdown.show");
    if (dropdown) dropdown.classList.remove("show");

    const rawName = (msg.author_name || msg.sender || '').replace(/"/g, '');
    const email = msg.from_email || msg.email_from || '';
    const fromLine = rawName && email ? `${rawName} <${email}>` : rawName || email || "(unknown)";

    const rawDate = msg.date || msg.date_received || msg.create_date;
    const dateStr = rawDate ? new Date(rawDate).toLocaleString('vi-VN') : '';

    const originalBody = msg.body || '';
    console.log("📨 Nội dung gốc trước xử lý:\n", originalBody);

    extractImagesAsCIDAttachments(originalBody).then(({ html, attachments }) => {
        const forwardedBody = `---------- Forwarded message ----------<br>
From: ${fromLine}<br>
Date: ${dateStr}<br>
Subject: ${msg.subject || ''}<br>
To: ${msg.to || ''}<br><br>
${html}`;

        console.log("📨 HTML sau khi xử lý ảnh:\n", forwardedBody);
        console.log("📎 Attachments đi kèm:\n", attachments);

        this.openComposeModal("forward", {
            subject: `Fwd: ${msg.subject || ''}`,
            body: forwardedBody,
            attachments: [...(msg.attachments || []), ...attachments],
            is_forward: true,
            date: rawDate || null,
        });

        setTimeout(() => {
            const composeBodyEl = document.querySelector(".compose-body");
            if (composeBodyEl) {
                console.log("📝 HTML trong compose thực tế:\n", composeBodyEl.innerHTML);
            }
        }, 500);
    });
}
