odoo.define('mass_mailing_contact_sort.sort_by_date', [], function () {
    "use strict";

    function sortCards(column, order) {
        const records = Array.from(column.querySelectorAll(".o_kanban_record"));
        const sorted = records.sort((a, b) => {
            const d1 = new Date(a.getAttribute("data-create-date"));
            const d2 = new Date(b.getAttribute("data-create-date"));
            return order === "asc" ? d1 - d2 : d2 - d1;
        });

        const container = column.querySelector(".o_kanban_records");
        sorted.forEach(card => container.appendChild(card));
    }

    function initSortButtons() {
        const columns = document.querySelectorAll(".o_kanban_group");

        columns.forEach(column => {
            const header = column.querySelector(".o_kanban_header");
            if (!header || header.querySelector(".sort-btn-group")) return;

            const group = document.createElement("div");
            group.className = "sort-btn-group";
            group.style.marginTop = "6px";
            group.innerHTML = `
                <button class="btn btn-sm btn-outline-secondary newest-btn">↓ New</button>
                <button class="btn btn-sm btn-outline-secondary oldest-btn">↑ Old</button>
            `;
            header.appendChild(group);

            group.querySelector(".newest-btn").onclick = () => sortCards(column, "desc");
            group.querySelector(".oldest-btn").onclick = () => sortCards(column, "asc");
        });
    }

    setTimeout(() => {
        initSortButtons();
    }, 1200);
});
