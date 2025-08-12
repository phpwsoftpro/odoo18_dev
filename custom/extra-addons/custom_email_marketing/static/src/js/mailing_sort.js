odoo.define('your_module.mailing_contact_kanban_sort', function (require) {
    "use strict";

    var KanbanColumn = require('web.KanbanColumn');

    KanbanColumn.include({
        renderElement: function () {
            this._super.apply(this, arguments);

            // Chỉ áp dụng với model mailing.contact
            if (this.modelName === 'mailing.contact') {
                this.addSortButton();
            }
        },

        addSortButton: function () {
            var self = this;
            var $header = this.$el.find('.o_kanban_header');

            if ($header.find('.sort-btn-group').length > 0) {
                return;
            }

            var $btnGroup = $(`
                <div class="sort-btn-group" style="margin-top: 4px;">
                    <button class="btn btn-sm btn-outline-secondary newest-btn" title="Sort Newest First">↓ New</button>
                    <button class="btn btn-sm btn-outline-secondary oldest-btn" title="Sort Oldest First">↑ Old</button>
                </div>
            `);

            $header.append($btnGroup);

            $btnGroup.find('.newest-btn').on('click', function () {
                self.sortCardsByDate('desc');
            });

            $btnGroup.find('.oldest-btn').on('click', function () {
                self.sortCardsByDate('asc');
            });
        },

        sortCardsByDate: function (order) {
            var $cards = this.$el.find('.o_kanban_record');
            var sorted = _.sortBy($cards, function (el) {
                var dateStr = $(el).attr('data-create-date');
                return new Date(dateStr);
            });

            if (order === 'desc') {
                sorted = sorted.reverse();
            }

            var $container = this.$el.find('.o_kanban_records');
            _.each(sorted, function (el) {
                $container.append(el); // Reorder card
            });
        },
    });
});
