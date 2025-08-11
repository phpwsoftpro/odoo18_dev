/** @odoo-module **/

export function fillComposeForm({ to = "", cc = "", bcc = "", subject = "", body = "" } = {}, editorInstance) {
    const toInput = document.querySelector(".compose-input.to");
    const ccInput = document.querySelector(".compose-input.cc");
    const bccInput = document.querySelector(".compose-input.bcc");
    const subjectInput = document.querySelector(".compose-input.subject");

    if (toInput) toInput.value = to;
    if (ccInput) ccInput.value = cc;
    if (bccInput) bccInput.value = bcc;
    if (subjectInput) subjectInput.value = subject;

    if (editorInstance && typeof editorInstance.setData === "function") {
        editorInstance.setData(body || "");
    } else {
        const textarea = document.querySelector("#compose_body");
        if (textarea) {
            textarea.value = body || "";
        }
    }
}
