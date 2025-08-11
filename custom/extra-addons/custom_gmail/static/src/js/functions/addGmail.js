// /** @odoo-module **/

// import { Component, useState } from "@odoo/owl";

// export class addGmail extends Component {
//     setup() {
//         this.state = useState({
//             accounts: [],
//             activeTabId: null,
//             messages: [],
//             selectedMessage: null,
//             currentThread: [],
//         });
//     }

//     async addGmailAccount() {
//         const popup = window.open("/gmail/auth/start", "_blank");
//         if (!popup) return;

//         const checkEmail = setInterval(async () => {
//             const res = await fetch("/gmail/current_user_info", {
//                 method: "POST",
//                 headers: {
//                     "Content-Type": "application/json",
//                     "X-Requested-With": "XMLHttpRequest",
//                 },
//                 body: JSON.stringify({
//                     jsonrpc: "2.0",
//                     method: "call",
//                     params: {},
//                 }),
//             });

//             const json = await res.json();
//             if (json.result?.status === "success" && Array.isArray(json.result.emails)) {
//                 clearInterval(checkEmail);

//                 json.result.emails.forEach((email) => {
//                     const exists = this.state.accounts.some((acc) => acc.email === email);
//                     if (!exists) {
//                         const newId = Date.now() + Math.floor(Math.random() * 1000);
//                         const newAccount = {
//                             id: newId,
//                             email,
//                             name: email.split("@")[0],
//                             initial: email[0].toUpperCase(),
//                             status: "active",
//                             messages: [],
//                             selectedMessage: null,
//                             currentThread: [],
//                         };
//                         this.state.accounts.push(newAccount);
//                         this.state.activeTabId = newId;
//                     } else {
//                         const existing = this.state.accounts.find((acc) => acc.email === email);
//                         this.state.activeTabId = existing.id;
//                     }
//                 });

//                 popup.close();
//             }
//         }, 2000);

//         popup.onbeforeunload = () => clearInterval(checkEmail);
//     }

//     switchTab(accountId) {
//         this.state.activeTabId = accountId;
//     }
// }

