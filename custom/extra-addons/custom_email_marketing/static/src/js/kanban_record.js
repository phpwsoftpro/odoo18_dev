odoo.define('mass_mailing_contact_sort.kanban_record', function (require) {
    "use strict";

    var KanbanRecord = require('web.KanbanRecord');

    KanbanRecord.include({
        start: function () {
            this._super.apply(this, arguments);
            var createDate = this.recordData.create_date;
            if (createDate) {
                this.$el.attr('data-create-date', createDate);
            }
        },
    });
});
