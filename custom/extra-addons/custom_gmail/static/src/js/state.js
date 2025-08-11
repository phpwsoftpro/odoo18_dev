/** @odoo-module **/
import { useState } from "@odoo/owl";

export function initialState() {
    return useState({
        accounts: [],
        activeTabId: null,
        email: "",
        selectedAccount: null,
        selectedMessage: null,
        currentThread: [],
        messages: [],
        messagesByEmail: {}, // ✅ THÊM DÒNG NÀY
        currentFolder: 'inbox',
        threads: {},
        showComposeModal: false,
        showDropdown: false,
        showDropdownVertical: false,
        showAccountDropdown: false,
        showAccounts: false,
        showSnoozeMenu: false,
        showSnoozePopup: false,
        showCc: false,
        showBcc: false,
        snoozeDate: null,
        snoozeTime: null,
        attachments: [],
        pagination: {
            currentPage: 1,
            pageSize: 15,
            totalPages: 1,
            total: 0,
        },

        // 🔽 BỔ SUNG DƯỚI ĐÂY
        showAllFolders: false,
        gmailFolders: [
            { id: "important", label: "Quan trọng", icon: "fa-tag" },
            { id: "chat", label: "Trò chuyện", icon: "fa-commenting-o" },
            { id: "scheduled", label: "Đã lên lịch", icon: "fa-calendar" },
            { id: "all_mail", label: "Tất cả thư", icon: "fa-envelope" },
            { id: "spam", label: "Thư rác", icon: "fa-exclamation-circle" },
            { id: "trash", label: "Thùng rác", icon: "fa-trash" },
            { id: "manage_labels", label: "Quản lý nhãn", icon: "fa-cog" },
            { id: "create_label", label: "Tạo nhãn mới", icon: "fa-plus" },

        ],
    });
}
