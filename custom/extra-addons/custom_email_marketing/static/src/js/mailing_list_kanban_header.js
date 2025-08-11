/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { KanbanHeader } from "@web/views/kanban/kanban_header";

patch(KanbanHeader.prototype, {
    setup() {
        super.setup();
        window.KanbanHeader = this;
    },

    sortByStartDate() {
        const allGroups = this.group.model.root.groups;

        for (const group of allGroups) {
            const records = group.list?.records || [];

            // Sắp xếp theo start_date (tăng dần)

            records.sort((a, b) => {
                const dA = a.data.start_date ? new Date(a.data.start_date) : new Date(0);
                const dB = b.data.start_date ? new Date(b.data.start_date) : new Date(0);
                return dB - dA;
            });

            // 👉 Bắt buộc phải gọi notify để re-render lại UI
            group.list.model.notify();

            console.log(`✅ Đã sort group "${group.displayName}" theo start_date`);
        }
    },

    get permissions() {
        const permissions = super.permissions;
        Object.defineProperty(permissions, "canEditAutomations", {
            get: () => true,
            configurable: true,
        });
        return permissions;
    },
});

// Chỉ hiển thị menu sort trong model "mailing.list"
registry.category("kanban_header_config_items").add(
    "sort_by_start_date",
    {
        label: "Sort by Start Date",
        method: "sortByStartDate",
        isVisible: ({ permissions, props }) =>
            permissions.canEditAutomations &&
            props.list.model.config.resModel === "mailing.list",
        class: "o_column_sort_start_date",
    },
    { sequence: 61 }
);

