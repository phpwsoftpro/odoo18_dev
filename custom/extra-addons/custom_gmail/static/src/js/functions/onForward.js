/** @odoo-module **/

// ✅ CHUẨN BỊ ẢNH TRONG EDITOR (tùy bạn có gọi hay không)
export function prepareImagesForSending() {
    const composeBodyEl = document.querySelector('.compose-body');
    if (!composeBodyEl) return;
    composeBodyEl.querySelectorAll("img[data-cid]").forEach(img => {
        const cid = img.getAttribute("data-cid");
        if (cid) img.setAttribute("src", `cid:${cid}`);
    });
}

// ✅ TRÍCH XUẤT ẢNH TỪ HTML GỐC ĐỂ GỬI KÈM (đổi src hiển thị = base64, gắn data-cid)
export async function extractImagesAsCIDAttachments(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html || "", "text/html");
    const imgs = doc.querySelectorAll("img");

    const attachments = []; // dạng { name, content(base64), mimetype, cid, inline:true }

    for (let i = 0; i < imgs.length; i++) {
        const img = imgs[i];
        const src = img.getAttribute("src") || "";

        // Chỉ xử lý ảnh nội bộ Odoo
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

                const match = base64Full.match(/^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/);
                if (!match) continue;

                const mimetype = match[1];
                const base64 = match[2];
                const ext = mimetype.split("/")[1] || "png";
                const cid = `inlineimage${i}@forward.local`;
                const filename = `image${i}.${ext}`;

                // Hiển thị trong editor: dùng base64 để người dùng thấy ảnh
                img.setAttribute("src", base64Full);
                img.setAttribute("data-cid", cid);
                img.setAttribute("data-original-src", base64Full);

                const existingStyle = img.getAttribute("style") || "";
                img.setAttribute(
                    "style",
                    `${existingStyle}; max-width:100%; height:auto; display:block; object-fit:contain; border:0;`
                );

                attachments.push({
                    name: filename,
                    content: base64,   // base64 thuần (không header data:)
                    mimetype,
                    cid,
                    inline: true,
                });
            } catch (err) {
                console.warn("⚠️ Không thể xử lý ảnh:", src, err);
            }
        }
    }

    return {
        html: doc.body ? doc.body.innerHTML : (html || ""),
        attachments, // để set vào this.state.attachments (onSendEmail sẽ chuyển sang File và gắn CID)
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

    extractImagesAsCIDAttachments(originalBody).then(({ html, attachments }) => {
        const forwardedBody = `---------- Forwarded message ----------<br>
From: ${fromLine}<br>
Date: ${dateStr}<br>
Subject: ${msg.subject || ''}<br>
To: ${msg.to || ''}<br><br>
${html}`;

        // Gộp attachments sẵn có (nếu có) + ảnh inline mới
        const mergedAttachments = [
            ...(this.state.attachments || []),
            ...(msg.attachments || []),
            ...attachments
        ];

        this.openComposeModal("forward", {
            subject: `Fwd: ${msg.subject || ''}`,
            body: forwardedBody,
            attachments: mergedAttachments, // sẽ được onSendEmail xử lý (File + inline manifest)
            is_forward: true,
            date: rawDate || null,
        });
    });
}
