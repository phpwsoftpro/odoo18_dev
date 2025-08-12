/** @odoo-module **/

let previousUrl = window.location.href;

function hasUrlChanged() {
    const currentUrl = window.location.href;
    if (currentUrl !== previousUrl) {
        previousUrl = currentUrl;
        return true;
    }
    return false;
}
function isCreateMode() {
    // Odoo create form thường không có id trong URL hoặc có 'new'
    const url = window.location.href;
    return url.includes("/new") || url.includes("create");
}

function activateCommentTab() {
    // Nếu đang ở create mode → không tự mở comment
    if (isCreateMode()) {
//        console.warn("🚫 Create mode detected. Skipping auto-comment.");
        return;
    }

    const noteBtn = document.querySelector(".o-mail-Chatter-logNote");
    const composer = document.querySelector(".o-mail-Composer");

    const invalidFields = document.querySelectorAll(".o_field_invalid");
    if (invalidFields.length > 0) {
//        console.warn("⚠️ Form contains invalid fields. Skipping auto-comment.");
        return;
    }

    if (noteBtn && (!composer || composer.classList.contains("d-none"))) {
        noteBtn.click();
    }
}


function updateChatterButtons() {
    const topbar = document.querySelector(".o-mail-Chatter-topbar");
    const sendBtn = document.querySelector(".o-mail-Chatter-sendMessage");
    const noteBtn = document.querySelector(".o-mail-Chatter-logNote");

    if (topbar && sendBtn && noteBtn) {
        // ❗ Nếu chưa có Note Email → thêm vào
        if (!topbar.querySelector(".o-mail-Chatter-noteEmail")) {
            const noteEmailBtn = noteBtn.cloneNode(true); // clone y nguyên nút Comment
            noteEmailBtn.classList.remove("o-mail-Chatter-logNote");
            noteEmailBtn.classList.add("o-mail-Chatter-noteEmail");
            noteEmailBtn.textContent = "Note Email";

            noteEmailBtn.addEventListener("click", () => {
                const composer = document.querySelector(".o-mail-Composer");
                const textarea = composer?.querySelector("textarea");

                if (composer && composer.classList.contains("d-none")) {
                    // Gọi nút comment để hiện composer (cách nhanh nhất)
                    noteBtn.click();
                }

                // ✏️ Gợi ý: bạn có thể xử lý composer nội dung riêng tại đây
                setTimeout(() => {
                    if (textarea) {
                        textarea.value = "[Note Email] ";  // Mở đầu nội dung hoặc flag xử lý
                        textarea.dispatchEvent(new Event("input")); // kích hoạt cập nhật
                    }
                }, 300);
            });

            // ✅ Chèn ngay sau nút Comment
            topbar.insertBefore(noteEmailBtn, sendBtn);
        }

        // Vị trí và styling chuẩn cho 2 nút gốc
        if (noteBtn.nextElementSibling !== sendBtn) {
            topbar.insertBefore(noteBtn, sendBtn);
        }

        sendBtn.classList.remove("btn-primary");
        sendBtn.classList.add("btn-secondary");

        noteBtn.classList.remove("btn-secondary");
        noteBtn.classList.add("btn-primary");

        // Nhãn
        if (noteBtn.textContent.trim() === "Log note") {
            noteBtn.textContent = "Comment";
        }
        if (sendBtn.textContent.trim() === "Send message") {
            sendBtn.textContent = "Send Email";
        }

        activateCommentTab();
        return true;
    }
    return false;
}




function observeChatter() {
    const target = document.body;
    const observer = new MutationObserver(() => {
        setTimeout(() => {
            updateChatterButtons();
        }, 200);
    });

    observer.observe(target, {
        childList: true,
        subtree: true,
    });
}

function observeComposerVisibility() {
    const chatter = document.querySelector(".o-mail-Chatter");
    if (!chatter) return;

    const observer = new MutationObserver(() => {
        const composer = document.querySelector(".o-mail-Composer");
        if (composer && composer.classList.contains("d-none")) {
            activateCommentTab();  // tự mở lại khi vừa gửi
        }
    });

    observer.observe(chatter, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["class"],
    });
}

document.addEventListener("DOMContentLoaded", () => {
    observeChatter();

    // Khi đổi URL (form mới, task khác...)
    setInterval(() => {
        if (hasUrlChanged()) {
            observeChatter();
            setTimeout(updateChatterButtons, 1000);
            setTimeout(observeComposerVisibility, 1500);
        }
    }, 1000);

    // Fallback
    setTimeout(() => {
        updateChatterButtons();
        observeComposerVisibility();
    }, 2000);
});
