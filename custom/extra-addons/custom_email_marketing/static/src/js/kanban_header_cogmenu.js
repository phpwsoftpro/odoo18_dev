/* @odoo-module */

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { KanbanHeader } from "@web/views/kanban/kanban_header";

patch(KanbanHeader.prototype, {
    setup() {
        super.setup();
        window.KanbanHeader = this;
    },

    sort_by_latest_date() {
        const group = this.group;
        const records = group.list?.records || [];

        records.sort((a, b) => {
            const dA = a.data.start_date ? new Date(a.data.start_date) : new Date(0);
            const dB = b.data.start_date ? new Date(b.data.start_date) : new Date(0);
            return dB - dA;
        });

        group.list.model.notify(); // chỉ notify lại group này
        console.log(`✅ Đã sort group "${group.displayName}" theo start_date`);
    },
    sort_by_oldest_date() {
        const group = this.group;
        const records = group.list?.records || [];

        records.sort((a, b) => {
            const dA = a.data.start_date ? new Date(a.data.start_date) : new Date(0);
            const dB = b.data.start_date ? new Date(b.data.start_date) : new Date(0);
            return dA - dB;
        });

        group.list.model.notify(); // chỉ notify lại group này
        console.log(`✅ Đã sort group "${group.displayName}" theo start_date`);
    },


    dateDeadlineSort() {
        const group = this.group;
        const records = group.list?.records || [];

        records.sort((a, b) => {
            const dateA = this._getDeadlineDate(a);
            const dateB = this._getDeadlineDate(b);
            return dateB - dateA;
        });

        group.list.model.notify();
        console.log(`✅ Đã sort group "${group.displayName}" theo deadline/remaining_days`);
    },

    _getDeadlineDate(record) {
        const dateDeadline = record.data?.date_deadline;
        if (dateDeadline) {
            return new Date(dateDeadline);
        }

        const remainingStr = record.data?.remaining_days;
        const timeStr = remainingStr?.split("→")[1]?.trim();
        if (timeStr) {
            return new Date(this._parseDateString(timeStr));
        }

        return new Date(0); // fallback nếu không có gì
    },

    _parseDateString(dateStr) {
        const [time, date] = dateStr.split(" ");
        if (!time || !date) return "1970-01-01T00:00:00";

        const [day, month, year] = date.split("/");
        return `${year}-${month}-${day}T${this._convertTo24H(time)}`;
    },

    _convertTo24H(timeStr) {
        const match = timeStr.match(/(\d{1,2}):(\d{2})(AM|PM)/i);
        if (!match) return "00:00:00";
        let [_, h, m, meridiem] = match;
        h = parseInt(h);
        if (meridiem.toUpperCase() === "PM" && h < 12) h += 12;
        if (meridiem.toUpperCase() === "AM" && h === 12) h = 0;
        return `${String(h).padStart(2, "0")}:${m}:00`;
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

registry.category("kanban_header_config_items").add(
    "sort_by_latest_date",
    {
        label: "Sort by latest date",
        method: "sort_by_latest_date",
        isVisible: ({ permissions, props }) =>
            permissions.canEditAutomations &&
            props.list.model.config.resModel === "project.task",
        class: "o_column_sort_by_latest_date",
    },
    { sequence: 61 }
);

registry.category("kanban_header_config_items").add(
    "sort_by_oldest_date",
    {
        label: "Sort by oldest date",
        method: "sort_by_oldest_date",
        isVisible: ({ permissions, props }) =>
            permissions.canEditAutomations &&
            props.list.model.config.resModel === "project.task",
        class: "o_column_sort_by_oldest_date",
    },
    { sequence: 61 }
);

registry.category("kanban_header_config_items").add(
    "start_date_sort",
    {
        label: "📅 Sort by Deadline",
        method: "dateDeadlineSort",
        isVisible: ({ permissions, props }) =>
            permissions.canEditAutomations &&
            props.list.model.config.resModel === "project.task",
        class: "o_column_test",
    },
    { sequence: 63 }
);