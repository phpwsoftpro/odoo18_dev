/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";

// Patch lại OWL Component bằng cách chặn thông báo lỗi khi record là mới (chưa có ID)
patch(FormRenderer.prototype, {
    _setInvalidField(field) {
        if (this.props.mode === "edit" && !this.props.record.resId) {
            // Nếu form chưa có resId => đang tạo mới => không hiện lỗi
            return;
        }
        // Gọi hàm gốc bình thường
        return FormRenderer.prototype._setInvalidField.wrapped.call(this, field);
    },
});
