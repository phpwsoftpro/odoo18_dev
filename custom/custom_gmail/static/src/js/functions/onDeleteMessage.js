/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";

export async function onDeleteMessage(ev, msg) {
    // Ngăn sự kiện dropdown đóng sớm
    ev.stopPropagation();
    // Xác nhận với người dùng
    if (!window.confirm("Bạn có chắc muốn xóa thư này không?")) {
        return;
    }
    try {
        // Gọi controller để xóa trên Gmail và Odoo
        const { success, error } = await rpc('/gmail/delete_message', { message_id: msg.id });
        if (!success) {
        return window.alert("Xóa thư thất bại: " + (error || "Không rõ nguyên nhân"));
        }
        await this.onRefresh();
    } catch (err) {
        console.error("Delete message failed:", err);
        window.alert("Xóa thư thất bại: " + (err.message || ""));
    }
}