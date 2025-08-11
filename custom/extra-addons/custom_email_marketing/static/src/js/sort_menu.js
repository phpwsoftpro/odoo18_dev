/** @odoo-module **/

import { registry } from "@web/core/registry";
import { KanbanColumn } from "@web/views/kanban/kanban_column";

export class CustomTaskKanbanColumn extends KanbanColumn {
    setup() {
        super.setup();
        this.sortOrder = null;
    }

    onSortChange(order) {
        this.sortOrder = order;
        this.model.root.env.config.context.kanban_sort_order = order;
        this.model.root.load();  // Force reload column
    }
}

// Đăng ký lại KanbanColumn nếu muốn override luôn
registry.category("views").add("kanban_column", CustomTaskKanbanColumn);
