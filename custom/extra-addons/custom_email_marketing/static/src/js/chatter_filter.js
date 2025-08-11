/** @odoo-module **/

// Biến để theo dõi URL trước đó, giúp phát hiện chuyển trang/task
let previousUrl = window.location.href;
// Flag đánh dấu đã thiết lập filter
let isFilterSetup = false;

function applyFilter() {
    const filterSelect = document.getElementById("chatter_filter_select");
    if (!filterSelect) return;

    const filterType = filterSelect.value;
    const chatter = document.querySelector(".o-mail-Chatter-content");
    if (!chatter) return;

    const messages = chatter.querySelectorAll('.o-mail-Message[aria-label="Message"]');
    const notes = chatter.querySelectorAll('.o-mail-Message[aria-label="Note"]');
    const noteEmails = chatter.querySelectorAll('.o-mail-Message[aria-label="Note Email"]'); // 👈 mới
    const systemNotifications = chatter.querySelectorAll('.o-mail-Message[aria-label="System notification"]');
    const activities = chatter.querySelectorAll(".o-mail-ActivityList");

    // Ẩn tất cả
    chatter.querySelectorAll(".o-mail-Message, .o-mail-ActivityList").forEach(el => {
        el.style.display = "none";
    });

    switch (filterType) {
        case "all":
            messages.forEach(el => el.style.display = "");
            notes.forEach(el => el.style.display = "");
            noteEmails.forEach(el => el.style.display = ""); // 👈 hiển thị Note Email
            activities.forEach(el => el.style.display = "");
            systemNotifications.forEach(el => el.style.display = "");
            break;
        case "message":
            messages.forEach(el => el.style.display = "");
            break;
        case "note":
            notes.forEach(el => el.style.display = "");
            break;
        case "note_email":
            noteEmails.forEach(el => el.style.display = "");
            break;
        case "activity":
            activities.forEach(el => el.style.display = "");
            systemNotifications.forEach(el => el.style.display = "");
            break;
    }
}


// Hàm kiểm tra xem URL đã thay đổi chưa (chuyển task)
function hasUrlChanged() {
    const currentUrl = window.location.href;
    if (currentUrl !== previousUrl) {
        previousUrl = currentUrl;
        return true;
    }
    return false;
}

function ensureNoteEmailOptionExists() {
    const filterSelect = document.getElementById("chatter_filter_select");
    if (!filterSelect) return;

    // Kiểm tra xem đã có option Note Email chưa
    const exists = Array.from(filterSelect.options).some(opt => opt.value === "note_email");
    if (!exists) {
        const option = document.createElement("option");
        option.value = "note_email";
        option.textContent = "Note Email";
        filterSelect.appendChild(option);
    }
}

function setupChatterFilter() {
    const filterSelect = document.getElementById("chatter_filter_select");
    const chatter = document.querySelector(".o-mail-Chatter-content");
    if (!filterSelect || !chatter) return;

    ensureNoteEmailOptionExists(); // 👈 gọi ở đây

    const isNewTask = hasUrlChanged();
    if (isNewTask || !isFilterSetup) {
        filterSelect.value = "note"; // mặc định
        isFilterSetup = true;
    }

    applyFilter();

    filterSelect.removeEventListener("change", applyFilter);
    filterSelect.addEventListener("change", applyFilter);
}


// Theo dõi DOM để phát hiện khi chatter load
document.addEventListener("DOMContentLoaded", () => {
    // Thiết lập ban đầu
    setupChatterFilter();
    
    // Sử dụng MutationObserver chỉ để phát hiện khi chatter mới xuất hiện
    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            // Chỉ xử lý khi có phần tử mới được thêm vào
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                // Kiểm tra xem chatter mới có xuất hiện không
                const chatterExists = document.querySelector(".o-mail-Chatter-content");
                const filterExists = document.getElementById("chatter_filter_select");
                
                if (chatterExists && filterExists) {
                    // Khi chuyển task hoặc lần đầu load, kiểm tra URL
                    if (hasUrlChanged()) {
                        isFilterSetup = false; // Reset flag để thiết lập lại filter
                    }
                    setupChatterFilter();
                    
                    // Không cần dừng observer vì chúng ta cần tiếp tục giám sát
                    // khi chuyển giữa các task khác nhau
                }
            }
        }
    });

    // Theo dõi thay đổi URL của Odoo (thường là khi chuyển task)
    window.addEventListener('hashchange', function() {
        isFilterSetup = false; // Đánh dấu cần thiết lập lại khi URL thay đổi
    });

    // Theo dõi toàn bộ DOM để phát hiện khi chatter xuất hiện
    observer.observe(document.body, { childList: true, subtree: true });
});

