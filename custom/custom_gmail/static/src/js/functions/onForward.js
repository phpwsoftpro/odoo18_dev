/** @odoo-module **/

export function onForward(ev, msg) {
    ev.stopPropagation();
    console.log("✅ Forwarding msg:", msg);


    // Xử lý From
    const rawName = (msg.author_name || msg.sender || '').replace(/"/g, '');  // loại bỏ dấu " nếu có
    const email = msg.from_email || msg.email_from || '';
    let fromLine = "From: ";
    if (rawName && email) {
        fromLine += `${rawName} <${email}>`;
    } else if (rawName) {
        fromLine += rawName;
    } else if (email) {
        fromLine += `<${email}>`;
    } else {
        fromLine += "(unknown)";
    }

    // Xử lý Date
    let dateStr = '';
    if (msg.date) {
        try {
            const parsed = Date.parse(msg.date);
            if (!isNaN(parsed)) {
                dateStr = new Date(parsed).toLocaleString('vi-VN');
            } else {
                dateStr = msg.date;
            }
        } catch (e) {
            dateStr = '';
        }
    }

    // Tạo nội dung forward
    const forwardedBody = `
        <br><br>---------- Forwarded message ---------<br>
        ${fromLine}<br>
        Date: ${dateStr}<br>
        Subject: ${msg.subject || ''}<br>
        To: ${msg.to || ''}<br><br>
        ${msg.body || ''}
    `;

    this.openComposeModal("forward", {
        subject: `Fwd: ${msg.subject || ''}`,
        body: forwardedBody,
        attachments: msg.attachments || [],
        is_forward: true,
        date: msg.date || msg.date_received || null,
    });
}
