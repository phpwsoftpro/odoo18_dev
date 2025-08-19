/** @odoo-module **/
import { Component, markup, onMounted, useEffect } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { initCKEditor, loadCKEditor } from "./ckeditor";
import { onAnalyze, onDeleteMessage, onForward, onReply, onReplyAll, onSendEmail, onSnooze, toggleStar } from "./functions/index";
import { openComposeModal } from "./functions/openComposeModal";
import { initialState } from "./state";
import { loadStarredState, saveStarredState } from "./storageUtils";
import template from "./template";
import {
    closeSnoozeMenu,
    closeSnoozePopup,
    getInitialBgColor,
    getInitialColor,
    getStatusText,
    iconByMime,
    isImage,
    onCloseCompose,
    onFileSelected,
    openFilePreview,
    openSnoozePopup,
    quickSnooze,
    removeAttachment,
    saveSnoozeDatetime,
    showSnoozeMenu,
    toggleAccounts,
    toggleDropdown,
    toggleDropdownAccount,
    toggleDropdownVertical,
    toggleSelect,
    toggleSelectAll,
    toggleThreadMessage
} from "./uiUtils";


async function getCurrentUserId() {
    const result = await rpc("/web/session/get_session_info");
    return result.uid;
}

function formatDate(dateStr) {
  const d = new Date(dateStr);
  const day   = d.getDate();
  const month = d.toLocaleString('en-US', { month: 'short' });
  const yyyy  = d.getFullYear();
  const hh    = String(d.getHours()).padStart(2, '0');
  const mm    = String(d.getMinutes()).padStart(2, '0');
  return `${day} ${month} ${yyyy}, ${hh}:${mm}`;
}

function timeAgo(dateStr) {
  const nowMs  = Date.now();
  const thenMs = new Date(dateStr).getTime();
  let diffSec  = Math.floor((nowMs - thenMs) / 1000);

  const units = [
    { name: 'year',   secs: 365*24*3600 },
    { name: 'month',  secs: 30*24*3600 },
    { name: 'day',    secs: 24*3600 },
    { name: 'hour',   secs: 3600 },
    { name: 'minute', secs: 60 },
    { name: 'second', secs: 1 },
  ];
  for (const u of units) {
    const val = Math.floor(diffSec / u.secs);
    if (val !== 0) {
      const label = val > 1 ? u.name + 's' : u.name;
      return `${val} ${label} ago`;
    }
  }
  return 'just now';
}

function formatInboxDate(dateStr) {
    const d   = new Date(dateStr);
    const now = new Date();

    // 1. Nếu cùng ngày
    if (d.toDateString() === now.toDateString()) {
        const HH = String(d.getHours()).padStart(2,'0');
        const mm = String(d.getMinutes()).padStart(2,'0');
        return `${HH}:${mm}`;
    }

    // 2. Nếu cùng năm
    if (d.getFullYear() === now.getFullYear()) {
        const MMM = d.toLocaleString('en-US', { month: 'short' }); // Jan, Feb,...
        const DD  = String(d.getDate()).padStart(2,'0');
        return `${MMM} ${DD}`;
    }

    // 3. Khác năm
    const MM = String(d.getMonth()+1).padStart(2,'0');
    const DD = String(d.getDate()).padStart(2,'0');
    const YY = String(d.getFullYear()).slice(-2);
    return `${MM}/${DD}/${YY}`;
}
function oa(x) {
  if (!x) return { name: "", address: "" };
  if (typeof x === "string") return { name: "", address: x }; // from là chuỗi
  const ea = x.emailAddress || x;
  return { name: ea.name || "", address: ea.address || "" };
}

function graphName(addr) {
  const n = (addr?.name || "").trim();
  const e = (addr?.address || "").trim();
  if (n) return n;
  if (e) return e.split("@")[0];
  return "Unknown Sender";
}
function joinEmails(list = []) {
    // list: [{ emailAddress: { name, address } }, ...]
    return list
      .map(it => {
        const a = oa(it);
        const n = (a.name || "").trim();
        const e = (a.address || "").trim();
        return (n && e) ? `${n} <${e}>` : (e || n || "");
      })
      .filter(Boolean)
      .join(", ");
}
function normalizeOutlookMessage(m) {
  // Lấy thông tin người gửi
  const fromObj = oa(m.from || m.sender);

  // Chọn thời điểm hiển thị
  const d =
    m.date ||
    m.date_received ||
    m.receivedDateTime ||
    m.sentDateTime ||
    "";

  // Chuẩn hóa TO/CC (chấp nhận cả chuỗi lẫn mảng {emailAddress:{...}})
  const toStr =
    m.email_receiver ||
    (typeof m.to === "string"
      ? m.to
      : Array.isArray(m.to)
      ? joinEmails(m.to)
      : joinEmails(m.toRecipients || []));

  const ccStr =
    m.email_cc ||
    (typeof m.cc === "string"
      ? m.cc
      : Array.isArray(m.cc)
      ? joinEmails(m.cc)
      : joinEmails(m.ccRecipients || []));

  const bodyHtml = m.body_html || m.body || "";

  return {
    ...m,
    type: "outlook",

    // Thread/conversation id (ưu tiên conversationId)
    thread_id:
      m.thread_id ||
      m.conversationId ||
      m.conversation_id ||
      m.internetMessageId ||
      m.id,

    // Tên hiển thị người gửi
    sender:
      (typeof m.sender === "string" && m.sender) ||
      graphName(fromObj) ||
      (m.email_sender ? m.email_sender.split("@")[0] : "Unknown Sender"),

    // Email người gửi
    email_sender:
      m.email_sender ||
      fromObj.address ||
      (typeof m.from === "string" ? m.from : ""),

    // Người nhận / CC dưới dạng chuỗi để UI dùng chung với Gmail
    email_receiver: toStr || "",
    email_cc: ccStr || "",
    email_bcc: m.email_bcc || "",

    // Thời gian hiển thị & format phụ
    date_received: d,
    dateInbox: d ? formatInboxDate(d) : "",
    dateDisplayed: d ? `${formatDate(d)} (${timeAgo(d)})` : "",

    // Body cho khung đọc (HTML)
    body_cleaned: bodyHtml,
    body: markup(bodyHtml),

    // Trạng thái
    is_read: m.is_read ?? m.isRead ?? false,
    is_starred_mail: m.is_starred_mail ?? false,
    is_sent_mail: (m.folder === "sent") || !!m.sentDateTime,

    showDropdown: false,
  };
}
function normalizeOutlookThreadItem(m) {
  const html = m.body_html || m.body || "";
  const d =
    m.date_received ||
    m.receivedDateTime ||
    m.sentDateTime ||
    m.date ||
    "";

  // NEW: convert list -> "Name <email>, Name2 <email2>"
  const toStr = Array.isArray(m.to) ? joinEmails(m.to) : (m.to || "");
  const ccStr = Array.isArray(m.cc) ? joinEmails(m.cc) : (m.cc || "");
  const fromStr = m.email_sender || (typeof m.from === "string" ? m.from : "");

  return {
    ...m,
    email_sender: fromStr,
    email_receiver: m.email_receiver || m.receiver || toStr,
    email_cc: m.email_cc || ccStr,
    email_bcc: m.email_bcc || m.bcc || "",

    sender: m.sender || (fromStr ? fromStr.split("@")[0] : "Unknown Sender"),

    body_cleaned: html,
    body: markup(html),

    date_received: d,
    dateInbox: d ? formatInboxDate(d) : "",
    dateDisplayed: d ? `${formatDate(d)} (${timeAgo(d)})` : "",

    showDropdown: false,
    type: "outlook",
  };
}
export class GmailInbox extends Component {
    setup() {

        this.state = initialState();

        // Các method binding
        console.log(removeAttachment);
        this.iconByMime = iconByMime.bind(this);
        this.isImage = isImage.bind(this);
        this.removeAttachment = (...args) => removeAttachment?.apply(this, args);
        this.onFileSelected = onFileSelected.bind(this);
        this.onSnooze = onSnooze.bind(this);
        // 👈 thêm dòng này
        this.showSnoozeMenu = showSnoozeMenu.bind(this);
        this.closeSnoozeMenu = closeSnoozeMenu.bind(this);
        this.boundCloseSnoozeMenu = closeSnoozeMenu.bind(this);
        this.openSnoozePopup = openSnoozePopup.bind(this);
        this.closeSnoozePopup = closeSnoozePopup.bind(this);
        this.quickSnooze = quickSnooze.bind(this);
        this.saveSnoozeDatetime = saveSnoozeDatetime.bind(this);
        // this.toggleStar = toggleStar.bind(this);
        this.toggleStar = (...args) => toggleStar.apply(this, args);
        this.onReply = onReply.bind(this);
        this.onReplyAll = onReplyAll.bind(this);
        this.onForward = onForward.bind(this);
        this.onDeleteMessage = onDeleteMessage.bind(this);
        this.toggleDropdown = toggleDropdown.bind(this);
        this.toggleDropdownVertical = toggleDropdownVertical.bind(this);
        this.toggleAccounts = toggleAccounts.bind(this);
        this.toggleDropdownAccount = toggleDropdownAccount.bind(this);
        this.toggleSelectAll = toggleSelectAll.bind(this);
        this.saveStarredState = saveStarredState.bind(this);
        this.loadStarredState = loadStarredState.bind(this);
        this.initCKEditor = initCKEditor.bind(this);
        this.loadCKEditor = loadCKEditor.bind(this);
        this.getInitialColor = getInitialColor.bind(this);
        this.getInitialBgColor = getInitialBgColor.bind(this);
        this.getStatusText = getStatusText.bind(this);
        this.toggleSelect = toggleSelect.bind(this);
        this.openComposeModal = openComposeModal.bind(this);
        this.toggleThreadMessage = toggleThreadMessage.bind(this);
        this.onCloseCompose = onCloseCompose.bind(this);
        this.onSendEmail = onSendEmail.bind(this);
        this.openFilePreview = openFilePreview;
        this.addGmailAccount = this._addGmailAccount;
        this.addOutlookAccount = this._addOutlookAccount;
        this.switchTab = this._switchTab.bind(this);
        this.state.isLoading = false;
        this.onRefresh = this.onRefresh.bind(this);
        this.showHeaderPopup = this.showHeaderPopup.bind(this);
        this.closeHeaderPopup = this.closeHeaderPopup.bind(this);
        this.switchFolder = this._switchFolder.bind(this);
        this.state.showHeaderPopup = false;
        this.state.popupMessage = null;
        this.onAnalyze = onAnalyze.bind(this);
        this.state.messagesByEmail = {};
        this.state.searchBarValue = "";
        this.switchFolder = this._switchFolder.bind(this);

        // Logic toggle sidebar "Hiện thêm"
        this.toggleShowAllFolders = () => {
            this.state.showAllFolders = !this.state.showAllFolders;
        };
        this.state.showCategoryLabels = false;
        this.toggleCategories = () => {
            this.state.showCategoryLabels = !this.state.showCategoryLabels;
            this.render();
        }
        this.onSearch = () => {
            const { from, to, subject, hasWords, dateWithin } = this.state.searchQuery;
            this.loadMessagesWithSearch(from, to, subject, hasWords, dateWithin);  // Call your search logic
        };

        this.state.showAdvancedSearch = false;  // Add this state for controlling the popup

        // Add this method to toggle the visibility of the advanced search form
        this.toggleAdvancedSearch = () => {
            this.state.showAdvancedSearch = !this.state.showAdvancedSearch;
            this.render();  // Re-render to reflect the state change
        };
        // ===== Build chuỗi query theo style Gmail
        this.buildSearchQueryString = (q) => {
            const parts = [];
            if (q.from) parts.push(`from:(${q.from})`);
            if (q.to) parts.push(`to:(${q.to})`);
            if (q.subject) parts.push(`subject:(${q.subject})`);
            if (q.hasWords) parts.push(q.hasWords);
            if (q.doesntHave) parts.push(`-${q.doesntHave}`);

            // size: Gmail dùng larger/smaller
            if (q.sizeValue) {
                const op = q.sizeOperator === "greater" ? "larger" : "smaller";
                parts.push(`${op}:${q.sizeValue}${(q.sizeUnit || "MB").toUpperCase()}`);
            }

            // date
            if (q.dateValue) parts.push(`before:${q.dateValue.replace(/-/g, "/")}`);
            if (q.dateWithin && q.dateWithin !== "1 day") {
                if (q.dateWithin === "1 week") parts.push("newer_than:7d");
                if (q.dateWithin === "1 month") parts.push("newer_than:30d");
            }

            // in:
            if (q.searchIn && q.searchIn !== "all") parts.push(`in:${q.searchIn}`);

            if (q.hasAttachment) parts.push("has:attachment");
            if (q.excludeChats) parts.push("-in:chats");
            return parts.join(" ").trim();
        };

        // ===== Tự động cập nhật preview mỗi khi user nhập trong popup (vì template dùng t-model)
        useEffect(
            () => {
                this.state.searchBarValue = this.buildSearchQueryString(this.state.searchQuery);
            },
            () => [
                this.state.searchQuery.from,
                this.state.searchQuery.to,
                this.state.searchQuery.subject,
                this.state.searchQuery.hasWords,
                this.state.searchQuery.doesntHave,
                this.state.searchQuery.sizeOperator,
                this.state.searchQuery.sizeValue,
                this.state.searchQuery.sizeUnit,
                this.state.searchQuery.dateWithin,
                this.state.searchQuery.dateValue,
                this.state.searchQuery.searchIn,
                this.state.searchQuery.hasAttachment,
                this.state.searchQuery.excludeChats,
            ],
        );


        // Example search query state
        this.state.searchQuery = {
            from: '',
            to: '',
            subject: '',
            hasWords: '',
            doesntHave: '',
            sizeOperator: 'greater',
            sizeValue: '',
            sizeUnit: 'MB',          
            dateWithin: '1 day',
            dateValue: '',
            searchIn: 'all',
            hasAttachment: false,
            excludeChats: false,
        };

        this.toggleSearchPopup = () => {
            this.state.showSearchPopup = !this.state.showSearchPopup;
            this.render();
            if (this.state.showSearchPopup) {
                setTimeout(() => {
                    document.addEventListener("mousedown", this._onClickOutsideSearchPopup);
                }, 0);
            } else {
                document.removeEventListener("mousedown", this._onClickOutsideSearchPopup);
            }            
        };
        this.state.showSearchPopup = false;
        
        this.onSearchAdvanced = async () => {
            const query = { ...this.state.searchQuery };

            // Kiểm tra hợp lệ sizeValue
            if (query.sizeValue && (!/^\d+$/.test(query.sizeValue) || Number(query.sizeValue) <= 0)) {
                alert("Size must be a positive number!");
                return;
            }

            this.state.isLoading = true;
            await this.loadMessagesWithAdvancedSearch(query);
            this.state.isLoading = false;
            this.state.showSearchPopup = false;
        };

        this.loadMessagesWithAdvancedSearch = async (query) => {
            const acc = this.state.accounts.find(a => a.id === this.state.activeTabId);
            if (!acc) return;

            const params = {
                account_id: parseInt(acc.id),
                from: query.from,
                to: query.to,
                subject: query.subject,
                hasWords: query.hasWords,
                doesntHave: query.doesntHave,
                sizeOperator: query.sizeOperator,
                sizeValue: query.sizeValue,
                sizeUnit: query.sizeUnit,
                dateWithin: query.dateWithin,
                dateValue: query.dateValue,
                searchIn: query.searchIn,
                hasAttachment: query.hasAttachment,
                excludeChats: query.excludeChats,
                page: 1,
                limit: this.state.pagination.pageSize,
            };

            const res = await rpc("/gmail/advanced_search", params);

            if (res && res.messages) {
                for (const msg of res.messages) {
                    msg.body_cleaned = msg.body;
                    msg.body = markup(msg.body);
                    msg.sender = msg.sender || msg.email_sender || "Unknown Sender";
                    msg.email_receiver = msg.email_receiver || '';
                    msg.email_cc = msg.email_cc || '';
                }
                this.state.messagesByEmail[acc.email] = res.messages;
                this.state.messages = res.messages;
                this.state.pagination.currentPage = 1;
                this.state.pagination.total = res.total;
                this.state.pagination.totalPages = Math.ceil(res.total / this.state.pagination.pageSize);
            } else {
                this.state.messages = [];
            }
            this.render();
        };
        this.clearSearchFilter = () => {
        this.state.searchQuery = {
            from: '',
            to: '',
            subject: '',
            hasWords: '',
            doesntHave: '',
            sizeOperator: 'greater',
            sizeValue: '',
            sizeUnit: 'MB',
            dateWithin: '1 day',
            dateValue: '',
            searchIn: 'all',
            hasAttachment: false,
            excludeChats: false,
        };
            this.state.searchBarValue = "";
            this.state.messages = [];
            this.render();
        };
        this._onClickOutsideVertical = (event) => {
            const dropdown = document.querySelector(".dropdown-menu-vertical");
            const button = document.querySelector(".icon-btn-option");

            // Nếu click vào chính dropdown hoặc nút toggle thì bỏ qua
            if (dropdown?.contains(event.target) || button?.contains(event.target)) return;

            this.state.showDropdownVertical = false;
            document.removeEventListener("click", this._onClickOutsideVertical);
            this.render();
        };

        this._onClickOutsideSearchPopup = (event) => {
            const popup = document.querySelector(".advanced-search-popup");
            const btn = document.querySelector(".gmail-advanced-icon");
            if (popup?.contains(event.target) || btn?.contains(event.target)) return;
            this.state.showSearchPopup = false;
            document.removeEventListener("mousedown", this._onClickOutsideSearchPopup);
            this.render();
        };

        // 🛑 Khôi phục từ localStorage (ban đầu)
        const savedAccounts = localStorage.getItem("gmail_accounts");
        if (savedAccounts) {
            this.state.accounts = JSON.parse(savedAccounts);
            if (this.state.accounts.length > 0) {
                this.state.activeTabId = this.state.accounts[0].id;
                this.loadMessages(this.state.accounts[0].email);
            }
        }
        // 🔁 Mount chính: Load account
        onMounted(async () => {
            const currentUserId = await getCurrentUserId();
            const gmailAccounts = await rpc("/gmail/my_accounts");
            const outlookAccounts = await rpc("/outlook/my_accounts");
            const mergedAccounts = [...gmailAccounts, ...outlookAccounts];

            if (mergedAccounts.length > 0) {
                this.state.accounts = mergedAccounts;
                this.state.activeTabId = mergedAccounts[0].id;
                this.loadMessages(mergedAccounts[0].email);
            } else {
                const savedAccounts = localStorage.getItem(`gmail_accounts_user_${currentUserId}`);
                if (savedAccounts) {
                    this.state.accounts = JSON.parse(savedAccounts);
                    if (this.state.accounts.length > 0) {
                        this.state.activeTabId = this.state.accounts[0].id;
                        this.loadMessages(this.state.accounts[0].email);
                    }
                }
            }

            // Xác thực email
            await this.loadAuthenticatedEmail();
            await this.loadOutlookAuthenticatedEmail();


            setInterval(() => {
                console.log("⏱️ Interval - currentFolder:", this.state.currentFolder);

                if (!document.hidden) {
                    if (this.state.currentFolder === "starred") {
                        console.log("🚫 Đang ở starred, không ping");
                        console.log("okela");
                        return;
                    }

                    console.log("✅ Đang ping...");
                    for (const account of this.state.accounts) {
                        if (account.type === "gmail") {
                            rpc("/gmail/session/ping", {
                                account_id: parseInt(account.id)
                            }).then((res) => {
                                if (res.has_new_mail) {
                                    this.state.loading = true;
                                    this.loadMessages(account.email, true).then(() => {
                                        this.state.loading = false;
                                        console.log(this.state.currentFolder)
                                        rpc("/gmail/clear_new_mail_flag", {
                                            account_id: parseInt(account.id),
                                        });
                                    });
                                }
                            });
                        }
                    }
                }
            }, 30000);


        });
    }

    async _switchFolder(folder) {
        console.log("📂 Switching folder to", folder);
        this.state.currentFolder = folder;

        const acc = this.state.accounts.find(a => a.id === this.state.activeTabId);
        if (!acc) return;

        // Gmail-only folders/labels
        if (folder === "starred" && acc.type === "gmail") {
            return this.loadGmailStarredMessages(acc.email);
        }
        if (folder === "all_mail" && acc.type === "gmail") {
            return this.loadGmailAllMailMessages(acc.email, 1);
        }
        if (
            acc.type === "gmail" &&
            ["important","chat","scheduled","spam","trash",
            "category_promotions","category_social",
            "category_updates","category_forums"].includes(folder)
        ) {
            return this.loadGmailMessages(acc.email, 1, folder.toUpperCase());
        }

        // ✅ ĐÃ GỬI cho cả hai loại tài khoản
        if (folder === "sent") {
            if (acc.type === "gmail")  return this.loadGmailSentMessages(acc.email, 1);
            if (acc.type === "outlook") return this.loadOutlookSentMessages(acc.email, 1);
        }

        // (tùy chọn) Drafts cho cả hai
        if (folder === "drafts") {
            if (acc.type === "gmail")  return this.loadGmailDraftMessages(acc.email, 1);
            if (acc.type === "outlook") return this.loadOutlookDraftMessages(acc.email, 1);
        }

        // Mặc định: Inbox theo loại account
        if (acc.type === "outlook") return this.loadOutlookMessages(acc.email, 1);
        return this.loadMessages(acc.email, true);
    }


    async onRefresh() {
        if (this.state.isRefreshing) {
            console.warn("🔄 Đang refresh, vui lòng chờ...");
            return;
        }

        const accountId = this.state.activeTabId;
        if (!accountId) {
            console.warn("❌ Không có account được chọn");
            return;
        }

        this.state.isRefreshing = true;
        try {
            const result = await rpc("/gmail/refresh_mail", {
                account_id: accountId,
            });

            if (result.status === "ok") {
                console.log("📬 Đã đồng bộ Gmail!");
                const account = this.state.accounts.find(a => a.id === accountId);
                if (account) {
                    // 👉 Gọi đúng folder đang mở
                    if (this.state.currentFolder === "starred") {
                        await this.loadGmailStarredMessages(account.email, 1);
                    } else if (this.state.currentFolder === "sent") {
                        await this.loadGmailSentMessages(account.email, 1);
                    } else if (this.state.currentFolder === "draft") {
                        await this.loadGmailDraftMessages(account.email, 1);
                    }
                    else {
                        await this.loadMessages(account.email, true);  // mặc định inbox
                    }
                }
            } else {
                console.warn("❌ Lỗi khi refresh:", result.error);
            }
        } catch (error) {
            console.error("❌ Lỗi khi gọi API refresh_mail:", error);
        } finally {
            this.state.isRefreshing = false;
        }
    }

    async loadGmailMessages(email, page = 1) {
        const account = this.state.accounts.find(acc => acc.email === email);
        if (!account) return;

        const res = await rpc("/gmail/messages", {
            account_id: parseInt(account.id),
            page: page,
            limit: this.state.pagination.pageSize,
        });
        // Lưu toàn bộ messages theo email
        this.state.messagesByEmail[email] = res.messages;
        this.state.messages = res.messages;

        // ✅ Phân nhóm theo thread_id
        this.state.threads = {};
        for (const msg of res.messages) {
            msg.dateInbox = formatInboxDate(msg.date_received);
            msg.dateDisplayed = formatDate(msg.date_received) + ' (' + timeAgo(msg.date_received) + ')';
            // ✅ Không làm sạch nữa, dùng nguyên gốc
            msg.body_cleaned = msg.body;  // có thể bỏ hẳn nếu không dùng cho preview

            // ✅ Vẫn cần markup để OWL t-raw hiểu đây là HTML
            msg.body = markup(msg.body);

            // ✅ Bổ sung trường
            msg.sender = msg.sender || msg.email_sender || "Unknown Sender";
            msg.email_receiver = msg.email_receiver || '';
            msg.email_cc = msg.email_cc || '';

            // ✅ Gom theo thread
            if (msg.thread_id) {
                if (!this.state.threads[msg.thread_id]) {
                    this.state.threads[msg.thread_id] = [];
                }
                this.state.threads[msg.thread_id].push(msg);
            }
        }

        // ✅ Sắp xếp thread
        for (const thread_id in this.state.threads) {
            this.state.threads[thread_id].sort((a, b) => new Date(a.date_received) - new Date(b.date_received));
        }

        // ✅ Lấy message mới nhất mỗi thread
        const latestMessagesPerThread = Object.values(this.state.threads).map(threadMsgs => {
            return threadMsgs[threadMsgs.length - 1];
        });

        this.state.messagesByEmail[email] = latestMessagesPerThread;
        this.state.messages = latestMessagesPerThread;

        // ✅ Phân trang
        this.state.pagination.currentPage = page;
        this.state.pagination.total = res.total;
        this.state.pagination.totalPages = Math.ceil(res.total / this.state.pagination.pageSize);
    }
    async loadGmailAllMailMessages(email, page = 1) {
        const account = this.state.accounts.find(acc => acc.email === email);
        if (!account) return;

        const res = await rpc("/gmail/all_mail_messages", {
            account_id: parseInt(account.id),
            page: page,
            limit: this.state.pagination.pageSize,
        });

        const threads = {};

        for (const msg of res.messages) {
            msg.body_cleaned = msg.body;
            msg.body = markup(msg.body);

            msg.sender = msg.sender || msg.email_sender || "Unknown Sender";
            msg.email_receiver = msg.email_receiver || '';
            msg.email_cc = msg.email_cc || '';

            if (msg.thread_id) {
                if (!threads[msg.thread_id]) {
                    threads[msg.thread_id] = [];
                }
                threads[msg.thread_id].push(msg);
            }
        }

        for (const thread_id in threads) {
            threads[thread_id].sort((a, b) => new Date(a.date_received) - new Date(b.date_received));
        }

        const latestMessagesPerThread = Object.values(threads).map(threadMsgs => {
            return threadMsgs[threadMsgs.length - 1];
        });

        this.state.threads = threads;
        this.state.messagesByEmail[email] = latestMessagesPerThread;
        this.state.messages = latestMessagesPerThread;

        this.state.pagination.currentPage = page;
        this.state.pagination.total = res.total;
        this.state.pagination.totalPages = Math.ceil(res.total / this.state.pagination.pageSize);
    }

    async loadGmailSentMessages(email, page = 1) {
        const account = this.state.accounts.find(acc => acc.email === email);
        if (!account) return;

        const res = await rpc("/gmail/sent_messages", {
            account_id: parseInt(account.id),
            page: page,
            limit: this.state.pagination.pageSize,
        });

        console.log("📤 Fetched sent messages", res);

        const threads = {};

        for (const msg of res.messages) {
            msg.body_cleaned = msg.body;
            msg.body = markup(msg.body);

            msg.sender = msg.sender || msg.email_sender || "Unknown Sender";
            msg.email_receiver = msg.email_receiver || '';
            msg.email_cc = msg.email_cc || '';

            if (!msg.thread_id) continue;
            if (!threads[msg.thread_id]) {
                threads[msg.thread_id] = [];
            }
            threads[msg.thread_id].push(msg);
        }

        // ✅ Sắp xếp từng thread theo thời gian tăng dần
        for (const thread_id in threads) {
            threads[thread_id].sort((a, b) => new Date(a.date_received) - new Date(b.date_received));
        }

        // ✅ Lấy message mới nhất mỗi thread
        let latestMessagesPerThread = Object.values(threads).map(threadMsgs => {
            return threadMsgs[threadMsgs.length - 1];
        });

        // ✅ Sắp xếp các thread theo thời gian giảm dần
        latestMessagesPerThread.sort((a, b) => new Date(b.date_received) - new Date(a.date_received));

        this.state.threads = threads;
        this.state.messagesByEmail[email] = latestMessagesPerThread;
        this.state.messages = latestMessagesPerThread;

        this.state.pagination.currentPage = page;
        this.state.pagination.total = res.total;
        this.state.pagination.totalPages = Math.ceil(res.total / this.state.pagination.pageSize);
    }

    async loadGmailDraftMessages(email, page = 1) {
        const account = this.state.accounts.find(acc => acc.email === email);
        if (!account) return;

        const res = await rpc("/gmail/draft_messages", {
            account_id: parseInt(account.id),
            page: page,
            limit: this.state.pagination.pageSize,
        });

        for (const msg of res.messages) {
            msg.body_cleaned = msg.body;
            msg.body = markup(msg.body);

            msg.sender = msg.sender || msg.email_sender || "Unknown Sender";
            msg.email_receiver = msg.email_receiver || '';
            msg.email_cc = msg.email_cc || '';
        }

        // ✅ Sort theo thời gian nếu có
        res.messages.sort((a, b) => new Date(b.date_received) - new Date(a.date_received));

        // ❌ Không gom thread nữa vì draft chưa có thread_id
        this.state.threads = {};  // hoặc giữ nguyên nếu không dùng

        this.state.messagesByEmail[email] = res.messages;
        this.state.messages = res.messages;

        this.state.pagination.currentPage = page;
        this.state.pagination.total = res.total;
        this.state.pagination.totalPages = Math.ceil(res.total / this.state.pagination.pageSize);
    }



    async loadGmailStarredMessages(email, page = 1) {
        const account = this.state.accounts.find(acc => acc.email === email);
        if (!account) return;

        const res = await rpc("/gmail/starred_messages", {
            account_id: parseInt(account.id),
            page: page,
            limit: this.state.pagination.pageSize,
        });

        console.log("⭐ Fetched starred messages:", res);

        this.state.threads = {};
        for (const msg of res.messages) {
            msg.body_cleaned = msg.body;
            msg.body = markup(msg.body);

            msg.sender = msg.sender || msg.email_sender || "Unknown Sender";
            msg.email_receiver = msg.email_receiver || '';
            msg.email_cc = msg.email_cc || '';

            if (msg.thread_id) {
                if (!this.state.threads[msg.thread_id]) {
                    this.state.threads[msg.thread_id] = [];
                }
                this.state.threads[msg.thread_id].push(msg);
            }
        }

        // Sắp xếp thread
        for (const thread_id in this.state.threads) {
            this.state.threads[thread_id].sort((a, b) => new Date(a.date_received) - new Date(b.date_received));
        }

        // Lấy message mới nhất mỗi thread
        const latestMessagesPerThread = Object.values(this.state.threads).map(threadMsgs => {
            return threadMsgs[threadMsgs.length - 1];
        });

        this.state.messagesByEmail[email] = latestMessagesPerThread;
        this.state.messages = latestMessagesPerThread;

        this.state.pagination.currentPage = page;
        this.state.pagination.total = res.total;
        this.state.pagination.totalPages = Math.ceil(res.total / this.state.pagination.pageSize);
    }

    async goNextPage() {
        if (this.state.pagination.currentPage < this.state.pagination.totalPages) {
            const acc = this.state.accounts.find(a => a.id === this.state.activeTabId);
            if (!acc) return;
            const next = this.state.pagination.currentPage + 1;

            if (acc.type === 'gmail') {
                if (this.state.currentFolder === 'sent')      return this.loadGmailSentMessages(acc.email, next);
                if (this.state.currentFolder === 'drafts')    return this.loadGmailDraftMessages(acc.email, next);
                if (this.state.currentFolder === 'starred')   return this.loadGmailStarredMessages(acc.email, next);
                if (this.state.currentFolder === 'all_mail')  return this.loadGmailAllMailMessages(acc.email, next);
                return this.loadGmailMessages(acc.email, next);
            } else if (acc.type === 'outlook') {
                if (this.state.currentFolder === 'sent')      return this.loadOutlookSentMessages(acc.email, next);
                if (this.state.currentFolder === 'drafts')    return this.loadOutlookDraftMessages(acc.email, next); // (nếu backend có)
                return this.loadOutlookMessages(acc.email, next); 
            }
        }
    }

    async goPrevPage() {
        if (this.state.pagination.currentPage > 1) {
            const acc = this.state.accounts.find(a => a.id === this.state.activeTabId);
            if (!acc) return;
            const prev = this.state.pagination.currentPage - 1;

            if (acc.type === 'gmail') {
                if (this.state.currentFolder === 'sent')     return this.loadGmailSentMessages(acc.email, prev);
                if (this.state.currentFolder === 'drafts')   return this.loadGmailDraftMessages(acc.email, prev);
                if (this.state.currentFolder === 'starred')  return this.loadGmailStarredMessages(acc.email, prev);
                if (this.state.currentFolder === 'all_mail') return this.loadGmailAllMailMessages(acc.email, prev);
                return this.loadGmailMessages(acc.email, prev);
            } else if (acc.type === 'outlook') {
                if (this.state.currentFolder === 'sent')     return this.loadOutlookSentMessages(acc.email, prev);
                if (this.state.currentFolder === 'drafts')   return this.loadOutlookDraftMessages(acc.email, prev); // (nếu backend có)
                return this.loadOutlookMessages(acc.email, prev);   
            }
        }
    }



    async loadOutlookMessages(email, page = 1) {
        const res = await rpc("/outlook/messages", {
            folder: "inbox",
            page,
            limit: this.state.pagination.pageSize,
            account_id: parseInt(this.state.activeTabId),
        });

        if (res.status !== "ok") {
            this.state.messages = [];
            return;
        }

        // Chuẩn hoá từng mail
        const normalized = (res.messages || []).map(normalizeOutlookMessage);

        // Gom theo thread_id (conversation)
        const threads = {};
        for (const msg of normalized) {
            const tid = msg.thread_id || msg.id;
            if (!threads[tid]) threads[tid] = [];
            threads[tid].push(msg);
        }

        // Sort trong từng thread theo thời gian tăng dần
        Object.values(threads).forEach(list =>
            list.sort((a, b) => new Date(a.date_received) - new Date(b.date_received))
        );

        // Lấy item mới nhất đại diện cho mỗi thread
        let latest = Object.values(threads).map(list => list[list.length - 1]);

        // Sort các thread theo thời gian giảm dần (giống inbox Gmail)
        latest.sort((a, b) => new Date(b.date_received) - new Date(a.date_received));

        this.state.threads = threads;
        this.state.messagesByEmail[email] = latest;
        this.state.messages = latest;

        this.state.pagination.currentPage = page;
        this.state.pagination.total = res.total ?? latest.length;
        this.state.pagination.totalPages = Math.ceil(
            this.state.pagination.total / this.state.pagination.pageSize
        );
    }

    async loadOutlookSentMessages(email, page = 1) {
        const res = await rpc("/outlook/sent_messages", {
            page,
            limit: this.state.pagination.pageSize,
        });

        if (res.status === "ok") {
            const messages = res.messages.map((msg) => {
                const html = msg.body_html || msg.body || "";
                const tmp = document.createElement("div");
                tmp.innerHTML = html;
                const preview = (tmp.textContent || "").trim().slice(0, 200);

                return {
                    ...msg,
                    type: "outlook",
                    body_cleaned: html,
                    body: markup(html),   // để t-raw hiển thị HTML
                    preview,
                };
            });

            this.state.messagesByEmail[email] = messages;
            this.state.messages = messages;

            // cập nhật phân trang (fallback nếu backend chưa trả total)
            this.state.pagination.currentPage = page;
            this.state.pagination.total = res.total ?? messages.length;
            this.state.pagination.totalPages = Math.ceil(
                this.state.pagination.total / this.state.pagination.pageSize
            );
        } else {
            console.warn("⚠️ Outlook sent fetch failed:", res.message);
            this.state.messages = [];
        }
    }


    async loadOutlookDraftMessages(email) {
        const res = await rpc("/outlook/draft_messages");
        if (res.status === "ok") {
            const messages = res.messages.map((m) => ({ ...m, type: "outlook" }));
            this.state.messagesByEmail[email] = messages;
            this.state.messages = messages;
        } else {
            console.warn("⚠️ Outlook draft fetch failed:", res.message);
            this.state.messages = [];
        }
    }

    async loadMessages(email, forceReload = false) {
        const acc = this.state.accounts.find(a => a.email === email);
        if (!acc) {
            console.warn("⚠️ Không tìm thấy account với email", email);
            return;
        }

        if (forceReload) {
            delete this.state.messagesByEmail[email];
        }

        if (!forceReload && this.state.messagesByEmail[email]) {
            const messages = this.state.messagesByEmail[email];
            // ✅ Re-patch toàn bộ để đảm bảo dữ liệu đủ cho template
            const patchedMessages = messages.map(msg => ({
                ...msg,
                body_cleaned: msg.body?.split('<div class="gmail_quote">')[0]
                    || msg.body?.replace(/<blockquote[\s\S]*?<\/blockquote>/gi, "")
                    || msg.body,
                sender: msg.sender || msg.email_sender || "Unknown Sender",
                email_receiver: msg.email_receiver || '',
                email_cc: msg.email_cc || '',
            }));

            this.state.messages = patchedMessages;

            // ✅ Khôi phục lại threads
            this.state.threads = {};
            for (const msg of patchedMessages) {
                if (msg.thread_id) {
                    if (!this.state.threads[msg.thread_id]) {
                        this.state.threads[msg.thread_id] = [];
                    }
                    this.state.threads[msg.thread_id].push(msg);
                }
            }

            // ✅ Sắp xếp lại thread
            for (const thread_id in this.state.threads) {
                this.state.threads[thread_id].sort((a, b) => new Date(a.date_received) - new Date(b.date_received));
            }

            return;
        }

        this.state.loading = true;
        try {
            if (acc.type === 'gmail') {
                if (this.state.currentFolder === 'sent') {
                    await this.loadGmailSentMessages(email);
                } else if (this.state.currentFolder === 'drafts') {
                    await this.loadGmailDraftMessages(email);
                }
                else if (this.state.currentFolder === 'starred') {
                    await this.loadGmailStarredMessages(email);
                }
                else if (this.state.currentFolder === "all_mail") {
                    await this.loadGmailMessages(acc.email, 1, "ALL_MAIL");
                }
                else {
                    await this.loadGmailMessages(email);
                }
            } else if (acc.type === 'outlook') {
                if (this.state.currentFolder === 'sent') {
                    await this.loadOutlookSentMessages(email);
                } else if (this.state.currentFolder === 'drafts') {
                    await this.loadOutlookDraftMessages(email);
                } else {
                    await this.loadOutlookMessages(email);
                }
            }
        } finally {
            this.state.loading = false;  // ✅ Tắt loading sau khi xong
        }
    }


    async loadAuthenticatedEmail() {
        try {
            const accountId = this.state.activeTabId;
            const account = this.state.accounts.find(acc => acc.id === accountId);
            if (!account || account.type !== 'gmail') {
            return; // Không phải Gmail thì bỏ qua
            }

            const result = await rpc("/gmail/user_email", { account_id: accountId });
            this.state.gmail_email = result.gmail_email || "No Email";
            console.log("✅ Gmail email loaded:", this.state.gmail_email);
        } catch (error) {
            console.error("❌ Lỗi khi gọi /gmail/user_email:", error);
            this.state.gmail_email = "Error loading Gmail";
        }
    }



    async loadOutlookAuthenticatedEmail() {
        try {
            const accountId = this.state.activeTabId;
            const account = this.state.accounts.find(acc => acc.id === accountId);
            if (!account || account.type !== 'outlook') {
                return;
            }

            const result = await rpc("/outlook/user_email", {
                account_id: accountId
            });
            this.state.outlook_email = result.outlook_email || "No Email";
        } catch (error) {
            console.error("❌ Lỗi khi gọi /outlook/user_email:", error);
            this.state.outlook_email = "Error loading Outlook";
        }
    }


    async onMessageClick(msg) {
        if (!msg) return;

        // Xác định account hiện tại
        const acc = this.state.accounts.find(a => a.id === this.state.activeTabId);

        // Nạp email đăng nhập nếu chưa có (theo loại account)
        if (!this.state.gmail_email && !this.state.outlook_email) {
            if (acc?.type === "gmail") {
                await this.loadAuthenticatedEmail();
            } else if (acc?.type === "outlook") {
                await this.loadOutlookAuthenticatedEmail();
            }
        }

        const normalize = (m) => ({
            ...m,
            body_cleaned: m.body, // giữ nguyên để t-raw hiển thị
            sender: m.sender || m.email_sender || "Unknown Sender",
            email_receiver: m.email_receiver || "",
            email_cc: m.email_cc || "",
            email_bcc: m.email_bcc || "",
            showDropdown: false,
            date: m.date || m.date_received || null,
        });

        const threadId = msg.thread_id;
        let thread = threadId ? this.state.threads?.[threadId] : null;

        // Hiển thị tạm thời những gì đang có
        this.state.currentThread =
            Array.isArray(thread) && thread.length ? thread.map(normalize) : [normalize(msg)];
        this.state.selectedMessage = msg;

        // === GMAIL: luôn fetch full thread để đảm bảo đủ conversation ===
        if (acc?.type === "gmail" && threadId) {
            try {
                const res = await rpc("/gmail/thread_detail", {
                    thread_id: threadId,
                    account_id: parseInt(this.state.activeTabId),
                });
                if (res.status === "ok") {
                    const full = res.messages.map(m => ({
                        ...m,
                        body_cleaned: m.body,
                        body: markup(m.body),
                        sender: m.sender || m.email_sender || "Unknown Sender",
                        email_receiver: m.email_receiver || "",
                        email_cc: m.email_cc || "",
                        email_bcc: m.email_bcc || "",
                        showDropdown: false,
                    }));
                    // cache lại thread đầy đủ
                    this.state.threads[threadId] = full;
                    // cập nhật khung đọc
                    this.state.currentThread = full;
                } else {
                    console.warn("⚠️ /gmail/thread_detail:", res.message);
                }
            } catch (err) {
                console.error("❌ /gmail/thread_detail error:", err);
            }
        }
        const isOutlook = msg.type === "outlook" || acc?.type === "outlook";
        if (isOutlook) {
            const norm = normalizeOutlookMessage(msg);
            this.updateMessage(norm);

            // hiển thị tạm thread từ cache (nếu có)
            let cachedThread = [];
            const tid = norm.thread_id;

            if (tid && this.state.threads?.[tid]?.length) {
            cachedThread = this.state.threads[tid].map(normalizeOutlookThreadItem);
            } else if (tid) {
            const activeEmail = this.state.accounts.find(a => a.id === this.state.activeTabId)?.email || "";
            const pool = (this.state.messagesByEmail[activeEmail] || []).concat(this.state.messages || []);
            cachedThread = pool
                .filter(x => (x.thread_id || x.id) === tid)
                .map(normalizeOutlookThreadItem)
                .sort((a, b) => new Date(a.date_received) - new Date(b.date_received));
            if (cachedThread.length) this.state.threads[tid] = cachedThread;
            } else {
            cachedThread = [normalizeOutlookThreadItem(norm)];
            }

            this.state.currentThread = cachedThread;
            this.state.selectedMessage = norm;

            if (tid) {
            try {
                const res = await rpc("/outlook/thread_detail", {
                thread_id: tid,
                account_id: parseInt(this.state.activeTabId),
                });

                if (res.status === "ok") {
                const full = (res.messages || [])
                    .map(normalizeOutlookThreadItem)
                    .sort((a, b) => new Date(a.date_received) - new Date(b.date_received));

                this.state.threads[tid] = full;
                this.state.currentThread = full;

                const sel = full.find(x => x.id === norm.id) || full[full.length - 1];
                if (sel) this.state.selectedMessage = sel;
                this.render();
                } else {
                console.warn("⚠️ /outlook/thread_detail:", res.message);
                }
            } catch (e) {
                console.error("❌ /outlook/thread_detail error:", e);
            }
            } else if (!norm.body_cleaned) {
            // fallback khi không có thread_id: lấy full body của 1 message
            try {
                const dres = await rpc("/outlook/message_detail", { message_id: norm.id });
                if (dres.status === "ok") {
                const html = (dres.content_type || "").toLowerCase() === "html"
                    ? (dres.body || dres.body_html || "")
                    : `<pre style="white-space:pre-wrap;margin:0">${dres.body || ""}</pre>`;
                const updated = normalizeOutlookThreadItem({ ...norm, body: html, body_html: html });
                this.updateMessage(updated);
                this.state.currentThread = [updated];
                this.state.selectedMessage = updated;
                this.render();
                }
            } catch (e) {
                console.error("❌ /outlook/message_detail error:", e);
            }
            }
        }
    }

    updateMessage(msg) {
        const index = this.state.messages.findIndex((m) => m.id === msg.id);
        if (index !== -1) {
            this.state.messages[index] = { ...msg };
        }

        if (msg.thread_id && this.state.threads[msg.thread_id]) {
            const threadIndex = this.state.threads[msg.thread_id].findIndex((m) => m.id === msg.id);
            if (threadIndex !== -1) {
                this.state.threads[msg.thread_id][threadIndex] = { ...msg };
            }
        }

        if (this.state.selectedMessage?.id === msg.id) {
            this.state.selectedMessage = { ...msg };
        }

        this.state.currentThread = this.state.currentThread.map(m =>
            m.id === msg.id ? { ...msg } : m
            
        );

        if ("starred" in msg) {
            this.saveStarredState();
        }
    }

    onComposeClick() {
        if (!this.state.showComposeModal) {
            // ✅ đang chuẩn bị mở, clear trước
            if (this.state.attachments && this.state.attachments.length) {
                console.log("🔥 Clear attachments before open compose");
                this.state.attachments.splice(0);
            }

            this.state.showCc = false;
            this.state.showBcc = false;
        }

        this.state.showComposeModal = !this.state.showComposeModal;

        if (this.state.showComposeModal) {
            setTimeout(() => initCKEditor(), 100);
        } else {
            if (window.editorInstance) {
                window.editorInstance.destroy();
                window.editorInstance = null;
            }

        }
        this.render();
    }


    _addGmailAccount = async () => {
        const popup = window.open("", "_blank", "width=700,height=800");
        popup.location.href = "/gmail/auth/start";

        if (!popup) {
            console.error("❌ Không thể mở popup xác thực Gmail.");
            return;
        }

        const handleMessage = async (event) => {
            if (event.data === "gmail-auth-success") {
                console.log("📩 Đã nhận gmail-auth-success từ popup");

                try {
                    // Gọi lại danh sách account sau khi xác thực
                    const gmailAccounts = await rpc("/gmail/my_accounts");
                    this.state.accounts = [...gmailAccounts, ...this.state.accounts.filter(a => a.type === "outlook")];
                    const newAccount = gmailAccounts[gmailAccounts.length - 1];
                    this.state.activeTabId = newAccount.id;
                    this.loadMessages(newAccount.email);

                    // ✅ Cập nhật localStorage
                    const currentUserId = await getCurrentUserId();
                    localStorage.setItem(
                        `gmail_accounts_user_${currentUserId}`,
                        JSON.stringify(this.state.accounts)
                    );
                } catch (error) {
                    console.error("❌ Lỗi khi lấy danh sách Gmail sau xác thực:", error);
                }

                window.removeEventListener("message", handleMessage);
            }
        };

        window.addEventListener("message", handleMessage);
    };


    _addOutlookAccount = async () => {
    const popup = window.open("", "_blank", "width=700,height=800");
    popup.location.href = "/outlook/auth/start";
    if (!popup) {
        console.error("❌ Không thể mở popup xác thực Outlook.");
        return;
    }

    const handleMessage = async (event) => {
        if (event.data !== "outlook-auth-success") return;

        try {
        // Lấy danh sách account từ server (id thật trong DB)
        const [gmailAccounts, outlookAccounts] = await Promise.all([
            rpc("/gmail/my_accounts"),
            rpc("/outlook/my_accounts"),
        ]);

        // Gộp & set state
        this.state.accounts = [...gmailAccounts, ...outlookAccounts];

        // Chọn account Outlook mới tạo (hoặc cái đầu tiên)
        const newAcc =
            outlookAccounts[outlookAccounts.length - 1] ||
            this.state.accounts.find((a) => a.type === "outlook");

        if (newAcc) {
            this.state.activeTabId = newAcc.id;       // <-- id DB thật
            await this.loadMessages(newAcc.email, true);
        }

        // Lưu lại cho lần sau
        const uid = await getCurrentUserId();
        localStorage.setItem(
            `gmail_accounts_user_${uid}`,
            JSON.stringify(this.state.accounts)
        );
        } catch (e) {
        console.error("❌ Lỗi sau khi xác thực Outlook:", e);
        } finally {
        window.removeEventListener("message", handleMessage);
        try { popup.close(); } catch (_) {}
        }
    };

    window.addEventListener("message", handleMessage);
    };
    _switchTab = (accountId) => {
        this.state.activeTabId = accountId;
        const acc = this.state.accounts.find((a) => a.id === accountId);
        if (acc) {
            // 👉 Kiểm tra loại account trước khi gọi route
            if (acc.type === 'gmail') {
                this.loadAuthenticatedEmail(); // gọi route Gmail
            } else if (acc.type === 'outlook') {
                this.loadOutlookAuthenticatedEmail(); // gọi route Outlook
            }

            this.loadMessages(acc.email);
        }
    };

    closeTab = async (accountId) => {
        const currentUserId = await getCurrentUserId();

        // Tìm account trong state
        const acc = this.state.accounts.find(a => a.id === accountId);
        if (!acc) {
            console.warn(`⚠️ Account ID ${accountId} not found.`);
            return;
        }

        try {
            // Ép accountId về số nguyên để tránh lỗi truy vấn
            const numericAccountId = parseInt(accountId);

            if (acc.type === 'gmail') {
                await rpc("/gmail/delete_account", { account_id: numericAccountId });
            } else if (acc.type === 'outlook') {
                await rpc("/outlook/delete_account", { account_id: numericAccountId });
            }
        } catch (error) {
            console.error("❌ Error deleting account:", error);
        }

        // Xoá account khỏi danh sách tab (state)
        const index = this.state.accounts.findIndex(a => a.id === accountId);
        if (index !== -1) {
            this.state.accounts.splice(index, 1);

            // Nếu tab active vừa bị đóng → chuyển sang tab đầu
            if (this.state.activeTabId === accountId) {
                const firstAccount = this.state.accounts[0];
                this.state.activeTabId = firstAccount ? firstAccount.id : null;
                if (firstAccount) {
                    await this.loadMessages(firstAccount.email);
                } else {
                    this.state.messages = [];
                }
            }

            // ✅ Cập nhật lại localStorage: lọc bỏ account bị xoá
            const savedKey = `gmail_accounts_user_${currentUserId}`;
            const savedAccounts = JSON.parse(localStorage.getItem(savedKey)) || [];
            const updatedAccounts = savedAccounts.filter(acc => acc.id !== accountId);
            localStorage.setItem(savedKey, JSON.stringify(updatedAccounts));
        }

        // ✅ Nếu là Gmail ping đang bật → clear interval
        if (this.gmailPingIntervalId) {
            clearInterval(this.gmailPingIntervalId);
            this.gmailPingIntervalId = null;
        }
    };
    toggleCcDetail(threadMsg) {
        if (!("showCcDetail" in threadMsg)) {
            threadMsg.showCcDetail = true;
        } else {
            threadMsg.showCcDetail = !threadMsg.showCcDetail;
        }
        this.render(); // Cập nhật lại template
    }

    getCCSummary(ccString) {
        if (!ccString) return "";
        const emails = ccString.split(',').map(e => e.trim());
        if (emails.length <= 2) return emails.join(', ');
        return `${emails[0]}, ${emails[1]}, ...`;
    }

    getToSummaryPlusCC(toString, ccString, currentUserEmail) {
        const toNames = this.getDisplayNamesFromList(toString, currentUserEmail, true);  // true = allow "tôi"
        const ccNames = this.getDisplayNamesFromList(ccString, currentUserEmail, false);

        const allNames = [...toNames, ...ccNames];
        if (allNames.length === 0) return "";
        if (allNames.length <= 2) return allNames.join(", ");
        return `${allNames[0]}, ${allNames[1]}, ...`;
    }

    getToSummary(addressString, currentUserEmail) {
        if (!addressString) return "";

        const addresses = addressString.split(",").map(a => a.trim());
        const normalizedCurrent = (currentUserEmail || "").trim().toLowerCase();

        const includesMe = addresses.some(email => email.toLowerCase().includes(normalizedCurrent));
        const others = addresses.filter(email => !email.toLowerCase().includes(normalizedCurrent));

        if (includesMe) {
            if (others.length === 0) return "tôi";
            if (others.length === 1) return `tôi, ${this.extractDisplayName(others[0])}`;
            return `tôi và ${others.length} người khác`;
        } else {
            if (addresses.length === 1) return this.extractDisplayName(addresses[0]);
            return `${this.extractDisplayName(addresses[0])} và ${addresses.length - 1} người khác`;
        }
    }

    extractDisplayName(emailString) {
        const match = emailString.match(/"?(.*?)"?\s*<(.+?)>/);
        if (match) {
            return match[1] || match[2].split("@")[0];
        }
        return emailString.split("@")[0];
    }
    getDisplayNamesFromList(addressString, currentUserEmail, allowToi = true) {
        if (!addressString) return [];
        const addresses = addressString.split(",").map(a => a.trim());
        const normalizedCurrent = (currentUserEmail || "").trim().toLowerCase();

        return addresses.map(addr => {
            if (allowToi && addr.toLowerCase().includes(normalizedCurrent)) {
                return "tôi";
            }
            const match = addr.match(/"?(.*?)"?\s*<(.+?)>/);
            return match ? (match[1] || match[2].split("@")[0]) : addr.split("@")[0];
        });
    }

    showHeaderPopup(threadMsg) {
        this.state.popupMessage = threadMsg;
        this.state.showHeaderPopup = true;
    }

    closeHeaderPopup() {
        this.state.showHeaderPopup = false;
    }



}

GmailInbox.template = template;
registry.category("actions").add("gmail_inbox_ui", GmailInbox);
export default GmailInbox; 