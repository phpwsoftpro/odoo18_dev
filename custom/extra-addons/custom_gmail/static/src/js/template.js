/** @odoo-module **/

import { xml } from "@odoo/owl";

export default xml`
<div class="gmail-root">
    <!-- Top Bar -->
    <div class="gmail-topbar">
        <div class="gmail-logo">
            <span class="gmail-logo-icon">
                <i class="fa fa-google"></i>
            </span>
            <span class="gmail-logo-text">Gmail</span>
        </div>
        <div class="gmail-search">
            <input type="text" placeholder="Search mail"
                t-model="state.searchBarValue"
                readonly="true"
                style="cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-right: 40px;"
                t-on-click="toggleSearchPopup"
            />
            <t t-if="state.searchBarValue">
                <button class="clear-search-btn" t-on-click="clearSearchFilter"
                    style="position:absolute;right:30px;top:5px;background:none;border:none;cursor:pointer;">
                    <i class="fa fa-times"></i>
                </button>
            </t>
            <button class="search-advanced-btn gmail-advanced-icon" t-on-click="toggleSearchPopup">

            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <g stroke="#444" stroke-width="2" stroke-linecap="round">
                <line x1="7" y1="7" x2="17" y2="7"/>
                <circle cx="10" cy="7" r="2" fill="#fff"/>
                <line x1="7" y1="12" x2="17" y2="12"/>
                <circle cx="14" cy="12" r="2" fill="#fff"/>
                <line x1="7" y1="17" x2="17" y2="17"/>
                <circle cx="12" cy="17" r="2" fill="#fff"/>
                </g>
            </svg>
            </button>
            <div t-if="state.showSearchPopup" class="advanced-search-popup">
                <div class="popup-body">
                    <div class="form-row">
                        <label>From:</label>
                        <input type="text" t-model="state.searchQuery.from" />
                    </div>
                    <div class="form-row">
                        <label>To:</label>
                        <input type="text" t-model="state.searchQuery.to" />
                    </div>
                    <div class="form-row">
                        <label>Subject:</label>
                        <input type="text" t-model="state.searchQuery.subject" />
                    </div>
                    <div class="form-row">
                        <label>Has the words:</label>
                        <input type="text" t-model="state.searchQuery.hasWords" />
                    </div>
                    <div class="form-row">
                        <label>Doesn't have:</label>
                        <input type="text" t-model="state.searchQuery.doesntHave" />
                    </div>
                    <div class="form-row">
                        <label>Date within:</label>
                        <select t-model="state.searchQuery.dateWithin" style="max-width:110px;">
                            <option value="1 day">1 day</option>
                            <option value="1 week">1 week</option>
                            <option value="1 month">1 month</option>
                        </select>
                        <input type="date"
                            t-model="state.searchQuery.dateValue"
                            t-att-max="(new Date()).toISOString().slice(0,10)"
                            style="max-width:150px; margin-left:8px;" />
                    </div>
                    <div class="form-row">
                        <label>Search:</label>
                        <select t-model="state.searchQuery.searchIn">
                            <option value="all">All Mail</option>
                            <option value="inbox">Inbox</option>
                            <option value="sent">Sent</option>
                            <option value="drafts">Drafts</option>
                            <option value="spam">Spam</option>
                        </select>
                    </div>
                    <div class="form-row" style="margin-top:8px;">
                        <label></label>
                        <input type="checkbox" t-model="state.searchQuery.hasAttachment" style="width:auto; margin-right:6px;"/>
                        <span style="margin-right:18px;">Has attachment</span>
                        <input type="checkbox" t-model="state.searchQuery.excludeChats" style="width:auto; margin-right:6px;"/>
                        <span>Don't include chats</span>
                    </div>
                </div>
                <div class="popup-footer">
                    <button class="search-btn" t-on-click="onSearchAdvanced">Search</button>
                </div>
            </div>
        </div>

        
        <div class="gmail-inbox-container">
            <div class="gmail-profile" t-on-click="() => this.toggleDropdownAccount()">
                <span class="user-icon">
                    <i class="fa fa-user-circle"></i>
                </span>
            </div>
            <div t-if="state.showAccountDropdown" class="account-dropdown-container">
                <div class="selected-account">
                    <div class="account-header">
                        <div class="email-info">
                            <div t-esc="state.selectedAccount.email" class="email-address"/>
                            <div t-if="state.selectedAccount.managed" t-esc="state.selectedAccount.managed" class="managed-by"/>
                        </div>
                        <button class="close-button" t-on-click="() => this.toggleDropdownAccount()">x</button>
                    </div>

                    <div class="account-greeting">
                        <div class="avatar-circle" t-attf-style="background-color: {{ this.getInitialBgColor(state.selectedAccount.initial) }}">
                            <span t-esc="state.selectedAccount.initial" t-attf-style="color: {{ this.getInitialColor(state.selectedAccount.initial) }}"/>
                        </div>
                        <div class="greeting-text">Hi, Robert!</div>
                    </div>

                    <button class="manage-account-btn">Manage your Google Account</button>

                    <div class="toggle-accounts" t-on-click="toggleAccounts">
                        <span t-if="state.showAccounts">Hide more accounts</span>
                        <span t-else="">Show more accounts</span>
                        <i t-if="state.showAccounts" class="fa fa-chevron-up"></i>
                        <i t-else="" class="fa fa-chevron-down"></i>
                    </div>

                    <!-- Other accounts list -->
                    <div t-if="state.showAccounts" class="accounts-list">
                        <t t-foreach="state.accounts.slice(1)" t-as="account" t-key="account.id">
                            <div class="account-item">
                                <div class="account-info">
                                    <div class="avatar-circle small" t-attf-style="background-color: {{ this.getInitialBgColor(account.initial) }}">
                                        <span t-esc="account.initial" t-attf-style="color: {{ this.getInitialColor(account.initial) }}"/>
                                    </div>
                                    <div class="account-details">
                                        <div class="account-name" t-esc="account.name"/>
                                        <div class="account-email" t-esc="account.email"/>
                                    </div>
                                </div>
                                <div class="account-status" t-esc="this.getStatusText(account.status)"/>
                            </div>

                            <div t-if="account.status === 'signed-out'" class="account-actions">
                                <button class="btn-sign-in">Sign in</button>
                                <button class="btn-remove">Remove</button>
                            </div>
                        </t>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="gmail-body">
        <!-- Left Sidebar -->
        <!-- Left Sidebar - Phần cần thay thế trong template -->
<div class="gmail-sidebar">
    <!-- Container cho nút compose - cố định ở trên -->
    <div class="compose-container">
        <button class="compose-btn" t-on-click="onComposeClick">
            <i class="fa fa-pencil"></i>
            <span>Soạn thư</span>
        </button>
    </div>
    
    <!-- Menu container có thể cuộn -->
    <ul class="gmail-menu">
        <li t-on-click="() => this.switchFolder('inbox')" t-att-class="{active: state.currentFolder === 'inbox'}">
            <i class="fa fa-inbox"></i>
            <span>Hộp thư đến</span>
        </li>
        <li t-on-click="() => this.switchFolder('starred')" t-att-class="{active: state.currentFolder === 'starred'}">
            <i class="fa fa-star-o"></i>
            <span>Có gắn dấu sao</span>
        </li>
        <li>
            <i class="fa fa-clock-o"></i>
            <span>Đã tạm ẩn</span>
        </li>
        <li t-on-click="() => this.switchFolder('sent')" t-att-class="{active: state.currentFolder === 'sent'}">
            <i class="fa fa-paper-plane"></i>
            <span>Đã gửi</span>
        </li>
        <li t-on-click="() => this.switchFolder('drafts')" t-att-class="{active: state.currentFolder === 'drafts'}">
            <i class="fa fa-file"></i>
            <span>Thư nháp</span>
        </li>
        
        <!-- Nút hiện thêm -->
        <li t-on-click="() => this.toggleShowAllFolders()">
            <i t-att-class="state.showAllFolders ? 'fa fa-chevron-up' : 'fa fa-chevron-down'"></i>
            <span t-if="state.showAllFolders">Thu gọn</span>
            <span t-else="">Hiện thêm</span>
        </li>

        <!-- 🔽 Hiển thị nếu đã click Hiện thêm -->
        <t t-if="state.showAllFolders">
            <t t-foreach="state.gmailFolders" t-as="folder" t-key="folder.id">
                <li
                    t-on-click="() => this.switchFolder(folder.id)"
                    t-att-class="{active: state.currentFolder === folder.id}">
                    <i t-att-class="'fa ' + folder.icon"></i>
                    <span t-esc="folder.label"/>
                </li>
            </t>
        </t>

        <!-- 📁 Nhóm Categories -->
            <li t-on-click="() => this.toggleCategories()" class="categories-folder">
                <i t-att-class="state.showCategoryLabels ? 'fa fa-folder-open' : 'fa fa-folder'"></i>
                <span>Categories</span>
            </li>

            <!-- Các nhãn con trong Categories -->
            <t t-if="state.showCategoryLabels">
                <li t-on-click="() => this.switchFolder('category_social')" t-att-class="{active: state.currentFolder === 'category_social'}" class="category_social">
                    <i class="fa fa-users"></i><span>Mạng xã hội</span>
                </li>
                <li t-on-click="() => this.switchFolder('category_updates')" t-att-class="{active: state.currentFolder === 'category_updates'}" class="category_updates">
                    <i class="fa fa-info-circle"></i><span>Cập nhật</span>
                </li>
                <li t-on-click="() => this.switchFolder('category_forums')" t-att-class="{active: state.currentFolder === 'category_forums'}" class="category_forums">
                    <i class="fa fa-comments"></i><span>Diễn đàn</span>
                </li>
                <li t-on-click="() => this.switchFolder('category_promotions')" t-att-class="{active: state.currentFolder === 'category_promotions'}" class="category_promotions">
                    <i class="fa fa-tag"></i><span>Quảng cáo</span>
                </li>
            </t>
    </ul>
</div>
        <div class="gmail-header">
            <t t-if="state.loading">
                <div class="simple-loading-banner">Loading...</div>
            </t>
   *         <!-- Filters & Actions -->
            <div class="header-actions">
                <div class="email-checkbox-all">
                    <input type="checkbox" id="selectAll" t-on-click="toggleSelectAll" style="cursor: pointer;"/>
                </div>
                <div class="dropdown-caret">
                    <button class="dropdown-icon" t-on-click="toggleDropdown">
                        <i class="fa fa-caret-down"></i>
                    </button>
                    <ul class="dropdown-menu-caret" t-attf-class="{{ state.showDropdown ? 'visible' : 'hidden' }}">
                        <li t-on-click="() => this.selectFilter('all')">All</li>
                        <li t-on-click="() => this.selectFilter('none')">None</li>
                        <li t-on-click="() => this.selectFilter('read')">Read</li>
                        <li t-on-click="() => this.selectFilter('unread')">Unread</li>
                        <li t-on-click="() => this.selectFilter('starred')">Starred</li>
                        <li t-on-click="() => this.selectFilter('unstarred')">Unstarred</li>
                    </ul>
                </div>

                <button class="icon-btn-reload" t-on-click="onRefresh">
                    <i class="fa fa-refresh"></i>
                </button>

                <button class="icon-btn-option" t-on-click="toggleDropdownVertical">
                    <i class="fa fa-ellipsis-v"></i>
                </button>

                <div class="dropdown-menu-vertical" t-attf-class="{{ state.showDropdownVertical ? 'visible' : 'hidden' }}">
                    <div class="dropdown-item">
                        <i class="fa fa-envelope-open-o"></i> Mark all as read
                    </div>
                    <t t-if="state.messages.some(m => m.selected)">
                        <div class="dropdown-item" t-on-click="() => this.showSnoozeMenu()">
                            <i class="fa fa-clock-o"></i> Snooze
                        </div>
                    </t>
                    <div class="dropdown-item disabled">
                        <em>Select messages to see more actions</em>
                    </div>
                </div>
                <t t-if="state.showSnoozeMenu">
                    <div class="snooze-menu"
                        style="position: absolute; top: 120px; left: 50%; transform: translateX(-50%);
                                background: white; border: 1px solid #ccc; border-radius: 8px;
                                box-shadow: 0 2px 10px rgba(0,0,0,0.2); width: 280px; z-index: 2001;">
                        <div style="padding: 12px 16px; font-weight: 500;">Snooze until...</div>

                        <div class="snooze-option" t-on-click="() => this.quickSnooze('today')"
                            style="display:flex; justify-content:space-between; padding:8px 16px; cursor:pointer;">
                            <span>Later today</span><span>6:00 PM</span>
                        </div>
                        <div class="snooze-option" t-on-click="() => this.quickSnooze('tomorrow')"
                            style="display:flex; justify-content:space-between; padding:8px 16px; cursor:pointer;">
                            <span>Tomorrow</span><span>8:00 AM</span>
                        </div>
                        <div class="snooze-option" t-on-click="() => this.quickSnooze('later_week')"
                            style="display:flex; justify-content:space-between; padding:8px 16px; cursor:pointer;">
                            <span>Later this week</span><span>Thu, 8:00 AM</span>
                        </div>
                        <div class="snooze-option" t-on-click="() => this.quickSnooze('weekend')"
                            style="display:flex; justify-content:space-between; padding:8px 16px; cursor:pointer;">
                            <span>This weekend</span><span>Sat, 8:00 AM</span>
                        </div>
                        <div class="snooze-option" t-on-click="() => this.quickSnooze('next_week')"
                            style="display:flex; justify-content:space-between; padding:8px 16px; cursor:pointer;">
                            <span>Next week</span><span>Mon, 8:00 AM</span>
                        </div>

                        <div style="border-top:1px solid #eee; margin-top:8px;"></div>

                        <div class="snooze-option" t-on-click="() => this.openSnoozePopup()"
                            style="display:flex; align-items:center; gap:8px; padding:8px 16px; cursor:pointer;">
                            <i class="fa fa-calendar"></i> <span>Pick date &amp; time</span>
                        </div>
                    </div>
                </t>
                <t t-if="state.showSnoozePopup">
                    <div class="snooze-popup-backdrop"
                        style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                                background: rgba(0,0,0,0.3); z-index: 2000;"
                        t-on-click="closeSnoozePopup">
                    </div>
                    <div class="snooze-popup"
                        style="position: fixed; top: 140px; left: 50%; transform: translateX(-50%);
                                background: white; border: 1px solid #ccc; border-radius: 8px; width: 300px;
                                box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 2001; padding: 20px;">
                        <div style="font-weight: 500; margin-bottom: 12px;">Pick date &amp; time</div>
                        <div style="display: flex; flex-direction: column; gap: 12px;">
                            <input type="date" t-model="state.snoozeDate" style="padding: 6px;"/>
                            <input type="time" t-model="state.snoozeTime" style="padding: 6px;"/>
                        </div>
                        <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px;">
                            <button t-on-click="closeSnoozePopup" style="padding: 6px 12px;">Cancel</button>
                            <button t-on-click="saveSnoozeDatetime" style="padding: 6px 12px; background: #4caf50; color: white; border: none; border-radius: 4px;">Save</button>
                        </div>
                    </div>
                </t>
                
                <div class="header-pagination" style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                    <div class="total-count" style="font-size: 14px;">
                        <t t-if="false">Tổng: <t t-esc="state.pagination.total"/> thư</t>
                    </div>
                    <div style="display: flex; justify-content: flex-end; align-items: center; gap: 8px; margin-right: 20px; margin-top: 8px;">
                        <button t-on-click="goPrevPage"
                                t-att-disabled="state.pagination.currentPage === 1"
                                style="background: none; border: none; font-size: 20px; cursor: pointer;">
                            ‹
                        </button>
                        <span style="font-size: 14px;">Trang <t t-esc="state.pagination.currentPage"/> / <t t-esc="state.pagination.totalPages"/>   Tổng: <t t-esc="state.pagination.total"/> </span>
                        <button t-on-click="goNextPage"
                                t-att-disabled="state.pagination.currentPage === state.pagination.totalPages"
                                style="background: none; border: none; font-size: 20px; cursor: pointer;">
                            ›
                        </button>
                    </div>
                </div>

            </div>

            <!-- Tabs -->
            <div class="gmail-tabs">
                <!-- Các tab account đang có -->
                <t t-foreach="state.accounts" t-as="acc" t-key="acc.id">
                    <div class="tab" t-att-class="acc.id === state.activeTabId ? 'tab active' : 'tab'" t-att-data-email="acc.email" t-on-click="() => this.switchTab(acc.id)">
                        <i class="fa fa-inbox"></i>
                        <t t-esc="acc.email"/>
                        <i class="fa fa-times close-tab" title="Đóng" style="margin-left: 8px; cursor: pointer;" t-on-click.stop="() => this.closeTab(acc.id)"></i>
                    </div>
                </t>

                <!-- Nút login Gmail -->
                <div class="tab login-tab" t-on-click="() => this.addGmailAccount()">
                    <img src="/custom_gmail/static/src/img/gmail_1.svg" alt="Gmail" class="icon-svg"/>
                </div>

                <!-- Nút login Outlook -->
                <div class="tab login-tab" t-on-click="() => this.addOutlookAccount()">
                    <img src="/custom_gmail/static/src/img/outlook.svg" alt="Outlook" class="icon-svg"/>
                </div>
            </div>
            <div class="tab-content">
                <div class="gmail-content">
                    <div class="content-container">
                        <div class="email-list">
                            <t t-if="state.messagesByEmail">
                                <t t-set="activeAccount" t-value="state.accounts.find(acc => acc.id === state.activeTabId)"/>
                                <t t-set="activeEmail" t-value="activeAccount ? activeAccount.email : ''"/>
                                <t t-set="activeMessages" t-value="state.messagesByEmail[activeEmail] || []"/>

                                <t t-foreach="activeMessages" t-as="msg" t-key="msg.id">
                                    <div class="email-item" t-att-class="'email-row ' + (msg.is_read ? 'read' : 'unread')" t-on-click="() => this.onMessageClick(msg)">

                                        <!-- Checkbox -->
                                        <div class="email-checkbox">
                                            <input type="checkbox" t-att-checked="msg.selected" t-on-click.stop="() => this.toggleSelect(msg)" />
                                        </div>

                                        <!-- Email Info -->
                                        <div class="email-info">
                                            <div class="email-header">
                                                <div class="email-from">
                                                    <t t-esc="msg.sender"/>
                                                </div>
                                                <div class="email-date">
                                                    <t t-esc="msg.dateInbox"/>
                                                </div>
                                            </div>
                                            <div class="email-content">
                                                <div class="email-subject">
                                                    <b>
                                                        <t t-esc="msg.subject"/>
                                                    </b>
                                                </div>
                                                <div class="email-preview">
                                                    <t t-esc="msg.preview"/>
                                                </div>
                                            </div>
                                        </div>
                                        <!-- Star & Actions -->
                                        <div class="email-star-actions">
                                            <div class="email-star" t-on-click.stop="() => this.toggleStar(msg)">
                                                <t t-if="msg.is_starred_mail">
                                                    <i class="fa fa-star" style="color: #e8e832;"></i>
                                                </t>
                                                <t t-else="">
                                                    <i class="fa fa-star-o"></i>
                                                </t>
                                            </div>
                                        </div>
                                    </div>
                                </t>
                            </t>
                            <t t-else="">
                                <div class="loading-or-error">Đang tải dữ liệu hoặc có lỗi xảy ra.</div>
                            </t>
                        </div>

                        <div class="email-detail">
                            <t t-if="state.selectedMessage">
                                <div class="detail-header">
                                    <h1 class="detail-subject">
                                        <t t-esc="state.selectedMessage.subject"/>
                                    </h1>
                                </div>
                                <div class="thread-container">
                                    <t t-foreach="state.currentThread" t-as="threadMsg" t-key="threadMsg.id">
                                        <div class="thread-message" t-att-class="{'current-message': threadMsg.id === state.selectedMessage.id, 'collapsed': threadMsg.collapsed}">
                                            <div class="message-header">
                                                <div class="sender-info">
                                                    <img t-att-src="threadMsg.avatar_url || '/path/to/default-avatar.png' || ''" alt="avatar" class="sender-avatar" />
                                                    <div class="sender-details">
                                                        <div class="sender-line">
                                                            <strong class="sender-name">
                                                                <t t-esc="threadMsg.sender"/>
                                                            </strong>
                                                        </div>
                                                        <div class="recipient-line">
                                                            <t t-if="this.state.currentFolder === 'sent'">
                                                                đến 
                                                                <t t-esc="threadMsg.to || 'Không rõ người nhận'" />
                                                            </t>
                                                            <t t-else="">
                                                                đến tôi
                                                            </t>
                                                            <span class="dropdown-arrow" t-on-click.stop="() => this.showHeaderPopup(threadMsg)">
                                                                <i class="fa fa-caret-down"></i>
                                                            </span>
                                                        </div>
                                                </div>
                                            </div>
                                            <div class="header-actions">
                                                <span class="email-date">
                                                    <t t-esc="threadMsg.dateDisplayed"/>
                                                </span>
                                                <button class="icon-btn star-btn" aria-label="Đánh dấu sao" t-on-click.stop="() => this.toggleStar(threadMsg)">
                                                    <i t-att-class="threadMsg.is_starred_mail ? 'fa fa-star' : 'fa fa-star-o'"></i>
                                                </button>



                                                <button class="icon-btn reply" title="Trả lời" aria-label="Phản hồi" t-on-click="(ev) => this.onReply(ev, threadMsg)">
                                                    <i class="fa fa-reply"></i>
                                                </button>

                                                <button class="icon-btn reply-all" aria-label="Trả lời tất cả" t-on-click="(ev) => this.onReplyAll(ev, threadMsg)">
                                                    <i class="fa fa-reply-all"></i>
                                                </button>

                                                <button class="action-btn analyze-email"
                                                        aria-label="Phân tích nội dung"
                                                        t-on-click="(ev) => this.onAnalyze(ev, state.selectedMessage)">
                                                    <i class="fa fa-magic"></i> Phân tích
                                                </button>

                                                <button class="icon-btn forward" title="Chuyển tiếp" aria-label="Chuyển tiếp" t-on-click="(ev) => this.onForward(ev, state.selectedMessage)">
                                                    <i class="fa fa-share"></i>
                                                </button>

                                                <button class="icon-btn more-btn"
                                                        style="outline: none; box-shadow: none; border: none;"
                                                        t-on-click.stop="() => threadMsg.showDropdown = !threadMsg.showDropdown">
                                                    <i class="fa fa-ellipsis-v"></i>
                                                </button>
                                                   <div class="dropdown-message-actions"
                                                        t-if="threadMsg.showDropdown"
                                                        style="position: absolute; top: 40px; right: 0; background: white;
                                                                border: none; outline: none;
                                                                border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); width: 220px; z-index: 2000;">
                                                        <ul style="list-style-type: none; padding: 8px 0; margin: 0;">
                                                            <li class="dropdown-item" t-on-click="(ev) => this.onReply(ev, threadMsg)">
                                                                <i class="fa fa-reply" style="margin-right: 8px;"></i> Reply
                                                            </li>
                                                            <li class="dropdown-item" t-on-click="(ev) => this.onReplyAll(ev, threadMsg)">
                                                                <i class="fa fa-reply-all" style="margin-right: 8px;"></i> Reply to all
                                                            </li>
                                                            <li class="dropdown-item" t-on-click="(ev) => this.onForward(ev, threadMsg)">
                                                                <i class="fa fa-share" style="margin-right: 8px;"></i> Forward
                                                            </li>
                                                            <li class="dropdown-item">
                                                                <i class="fa fa-filter" style="margin-right: 8px;"></i> Filter messages like this
                                                            </li>
                                                            <li class="dropdown-item" t-on-click="() => window.print()">
                                                                <i class="fa fa-print" style="margin-right: 8px;"></i> Print
                                                            </li>
                                                            <li class="dropdown-item" t-on-click="(ev) => this.onDeleteMessage(ev, threadMsg)">
                                                                <i class="fa fa-trash" style="margin-right: 8px;"></i> Delete this message
                                                            </li>
                                                        </ul>
                                                    </div>
                                            </div>
                                        </div>

                                        <div class="message-content">
                                            
                                            <t t-raw="threadMsg.body"/>
                                        </div>
                                        <style>
                                            .attachments { margin-top: 12px; padding-top: 8px; border-top: 1px solid #e5e7eb; }
                                            .attachments-title { font-size: 13px; font-weight: 500; color: #555; margin-bottom: 8px; }
                                            .attachments-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; }
                                            .attachment-card { position: relative; border: 1px solid #e6e8eb; border-radius: 10px; background: #fff; padding: 10px; transition: box-shadow .15s ease, transform .15s ease, border-color .15s ease; display: flex; flex-direction: column; min-height: 140px; }
                                            .attachment-card:hover { box-shadow: 0 6px 16px rgba(0,0,0,.08); transform: translateY(-1px); border-color: #d8dbe0; }
                                            .attachment-card.image .attachment-thumb { display: block; width: 100%; max-width: 160px; height: auto; max-height: 120px; object-fit: cover; border-radius: 8px; margin: 0 auto 8px auto; background: #f6f7f9; }
                                            .file-icon { font-size: 28px; color: #6b7280; margin-bottom: 6px; }
                                            .file-meta { display: flex; flex-direction: column; gap: 2px; }
                                            .file-meta .file-name { font-size: 13px; font-weight: 600; color: #1f2937; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
                                            .file-meta .file-size { font-size: 12px; color: #6b7280; }
                                            .attachment-actions { margin-top: auto; display: flex; gap: 8px; flex-wrap: wrap; }
                                            .attachment-actions .btn { display: inline-flex; align-items: center; border: 1px solid #e5e7eb; background: #fafafa; color: #374151; font-size: 12px; padding: 3px 8px; border-radius: 5px; text-decoration: none; cursor: pointer; transition: background .15s ease, border-color .15s ease; }
                                            .attachment-actions .btn:hover { background: #f3f4f6; border-color: #e0e2e7; }
                                            .attachment-actions .btn:active { transform: translateY(1px); }
                                            </style>

                                            <t t-if="(threadMsg.attachments or []).length &gt; 0">
                                                <div class="attachments">
                                                    <div class="attachments-title">
                                                        <t t-esc="threadMsg.attachments.length"/> attachment
                                                        <t t-if="threadMsg.attachments.length &gt; 1">s</t>
                                                    </div>
                                                    <div class="attachments-grid">
                                                        <t t-foreach="threadMsg.attachments" t-as="att" t-key="att.id">
                                                            <div class="attachment-card" t-att-class="this.isImage(att.mimetype) ? 'image' : 'file'">
                                                                <t t-if="this.isImage(att.mimetype)">
                                                                    <a t-att-href="att.url" target="_blank" rel="noopener">
                                                                        <img t-att-src="att.url" alt="preview" class="attachment-thumb"/>
                                                                    </a>
                                                                </t>
                                                                <t t-else="">
                                                                    <div class="file-icon"><i t-att-class="this.iconByMime(att)"></i></div>
                                                                    <div class="file-meta">
                                                                        <div class="file-name" t-att-title="att.name"><t t-esc="att.name"/></div>
                                                                        <div class="file-size">mimetype: <t t-esc="att.mimetype or 'unknown'"/></div>
                                                                    </div>
                                                                </t>
                                                                <div class="attachment-actions">
                                                                    <a class="btn btn-xs" t-att-href="att.url" target="_blank" rel="noopener">Open</a>
                                                                    <a class="btn btn-xs" t-att-href="att.download_url or (att.url + '&amp;download=true')">Download</a>
                                                                </div>
                                                            </div>
                                                        </t>
                                                    </div>
                                                </div>
                                            </t>
                                    </div>
                                </t>
                            </div>

                        </t>
                        <t t-if="!state.selectedMessage">
                            <div class="no-message">
                                <div class="no-message-icon">
                                    <i class="fa fa-envelope-o"></i>
                                </div>
                                <p>Không có cuộc trò chuyện nào được chọn.</p>
                                <p>Hãy chọn một email để xem chi tiết.</p>
                            </div>
                        </t>
                    </div>
                </div>
            </div>
        </div>

    </div>
</div>
<t t-if="state.showHeaderPopup and state.popupMessage">
    <div class="email-header-popup-backdrop" t-on-click="closeHeaderPopup"
         style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.3); z-index: 1000;">
    </div>
    <div class="email-header-popup"
         style="position: fixed; top: 100px; left: 50%; transform: translateX(-50%); z-index: 1001;
                background: white; padding: 16px; border: 1px solid #ccc; border-radius: 8px; width: 450px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2); font-size: 14px;">
        <div><strong>từ:</strong> <t t-esc="state.popupMessage.sender" /></div>
        <div>
            <strong>đến:</strong>
            <t t-esc="this.state.accounts.find(acc => acc.id === this.state.activeTabId)?.email || 'Không xác định'" />
        </div>
        <t t-if="state.popupMessage.email_cc">
            <t t-set="ccList" t-value="state.popupMessage.email_cc ? state.popupMessage.email_cc.split(',') : []" />
            <div>
                <strong>cc:</strong>
                <t t-if="ccList.length &gt; 0">
                    <span style="margin-left: 4px; white-space: nowrap;">
                        <t t-esc="ccList[0].trim()" />
                    </span>
                </t>
            </div>
            <t t-if="ccList.length &gt; 1">
                <t t-foreach="ccList.slice(1)" t-as="cc" t-key="cc">
                    <div style="margin-left: 36px; white-space: nowrap;">
                        <t t-esc="cc.trim()" />
                    </div>
                </t>
            </t>
        </t>

        <div><strong>ngày:</strong> <t t-esc="state.popupMessage.date_received" /></div>
        <div><strong>tiêu đề:</strong> <t t-esc="state.popupMessage.subject" /></div>
        <div><strong>gửi bởi:</strong> gmail.com</div>
        <div><strong>xác thực bởi:</strong> gmail.com</div>
    </div>
</t>
<!-- Compose Modal -->
<t t-if="state.showComposeModal">
    <div class="compose-modal">
        <div class="compose-modal-header">
            <h3>Thư mới</h3>
            <div class="header-actions">
                <button style="font-size: 30px;">−</button>
                <button style="font-size: 30px;">↗</button>
                <button t-on-click="onCloseCompose" style="font-size: 30px;">×</button>
            </div>
        </div>
        <div class="compose-modal-body">
            <div class="compose-field">
                <label>Đến</label>
                <input type="text" class="compose-input to" name="to"/>
                <div class="cc-bcc">
                    <t t-if="!state.showCc">
                        <span t-on-click="() => state.showCc = true" style="cursor:pointer;">Cc</span>
                    </t>
                    <t t-if="!state.showBcc">
                        <span t-on-click="() => state.showBcc = true" style="margin-left:10px; cursor:pointer;">Bcc</span>
                    </t>
                </div>
            </div>
            <t t-if="state.showCc">
                <div class="compose-field">
                    <label>Cc</label>
                    <input type="text" class="compose-input cc" name="cc"/>
                </div>
            </t>

            <t t-if="state.showBcc">
                <div class="compose-field">
                    <label>Bcc</label>
                    <input type="text" class="compose-input bcc" name="bcc"/>
                </div>
            </t>
            <div class="compose-field">
                <label>Tiêu đề</label>
                <input type="text" class="compose-input subject" name="subject"/>
            </div>
            <div class="compose-textarea-container">
                <textarea id="compose_body" class="compose-textarea"></textarea>
            </div>
            <!-- 🔁 Signature (dynamic from active account) -->
                <t t-set="acc" t-value="this.state.accounts.find(a => a.id === this.state.activeTabId)"/>
                    <div class="email-signature" style="margin-top:16px; padding-top:12px; border-top:1px solid #ddd;">
                        <table style="border:none; font-family:Arial, sans-serif; font-size:14px;">
                            <tr>
                            <td style="padding-right:12px; vertical-align:top;">
                                <td style="padding-right:12px;vertical-align:top;">
                                    <img
                                        class="signature-avatar"
                                        t-att-src="(acc &amp;&amp; acc.avatar_url) ? acc.avatar_url : '/web/static/img/placeholder.png'"
                                        alt="Signature Avatar"
                                        style="width:90px;height:90px;border-radius:50%;object-fit:cover;"
                                        t-att-data-cid="'sig-avatar-' + (acc ? acc.id : '0')"
                                        />
                                </td>
                            </td>
                            <td style="vertical-align:top; line-height:1.4;">
                                <div style="font-weight:bold; font-size:16px; color:#000;">
                                <t t-esc="acc and acc.user_id and acc.user_id.name or 'User Name'"/>
                                </div>
                                <div style="color:#555;">
                                <t t-esc="acc and acc.email or 'user@example.com'"/>
                                </div>
                                <div style="font-weight:bold; color:#000;">WSOFTPRO</div>
                                <hr style="border:none; border-top:1px solid #ccc; margin:8px 0;" />
                                <div>📞 (+84) 393 558 941</div>
                                <div>✉️ <t t-esc="acc and acc.email or 'user@example.com'"/></div>
                                <div>🌐 <a href="https://wsoftpro.com/" target="_blank" style="color:#0066cc;">https://wsoftpro.com/</a></div>
                                <div>📍 7/26 Nguyen Hong, Dong Da, Hanoi, Vietnam</div>
                            </td>
                            </tr>
                        </table>
                        </div>
            <div class="compose-field">
                <div>
                    <label for="file_attachments" class="btn btn-sm btn-secondary" style="cursor: pointer;">
                        📎 Chọn tệp
                    </label>
                    <input id="file_attachments" type="file" multiple="multiple" style="display: none;"
                        t-on-change="onFileSelected"/>
                </div>

                <ul class="attachment-list" t-if="state.attachments.length" style="margin-top:10px;">
                    <t t-foreach="state.attachments or []" t-as="file" t-key="file.name">
                        <li style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid #eee;">
                            <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:250px;">
                                <t t-esc="file.name"/>
                            </span>
                            <span style="color:#555;margin-left:6px;">
                                (<t t-esc="file.sizeText"/>)
                            </span>
                            <button t-on-click="() => this.removeAttachment(file)"
                                    style="background:none;border:none;color:#888;cursor:pointer;font-size:16px;">
                                ×
                            </button>
                        </li>
                    </t>
                </ul>
            </div>
        </div>

        <div class="compose-modal-footer">
            <div class="left-buttons">
                <button class="send-btn" t-on-click="onSendEmail">Gửi</button>
                <button class="save-draft-btn" t-on-click="onSaveDraft" title="Lưu nháp">
                    <i class="fa fa-floppy-o"></i>
                </button>
            </div>
            <button class="trash-icon" t-on-click="onCloseCompose">
                <i class="fa fa-trash"></i>
            </button>
        </div>
    </div>
</t>
</div>

`;
