/** @odoo-module **/

export function onReplyAll(ev, msg) {
    ev.stopPropagation();
    this.openComposeModal("replyAll", msg);
}