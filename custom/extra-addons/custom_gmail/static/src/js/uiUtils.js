/** @odoo-module **/
// true nếu là ảnh => show thumbnail
export function isImage(mimetype) {
    return typeof mimetype === 'string' && mimetype.startsWith('image/');
}

// chọn icon theo mimetype/tên file
export function iconByMime(att) {
    const mt = (att?.mimetype || '').toLowerCase();
    const name = (att?.name || '').toLowerCase();

    if (mt.includes('pdf') || name.endsWith('.pdf')) return 'fa fa-file-pdf-o';
    if (mt.includes('zip') || mt.includes('compressed') || /\.(zip|rar|7z|tar|gz)$/.test(name)) return 'fa fa-file-archive-o';
    if (mt.includes('word') || /\.(doc|docx)$/.test(name)) return 'fa fa-file-word-o';
    if (mt.includes('excel') || /\.(xls|xlsx|csv)$/.test(name)) return 'fa fa-file-excel-o';
    if (mt.includes('powerpoint') || /\.(ppt|pptx)$/.test(name)) return 'fa fa-file-powerpoint-o';
    if (mt.includes('json') || name.endsWith('.json')) return 'fa fa-file-code-o';
    if (mt.startsWith('text/') || name.endsWith('.txt')) return 'fa fa-file-text-o';
    if (mt.startsWith('audio/')) return 'fa fa-file-audio-o';
    if (mt.startsWith('video/')) return 'fa fa-file-video-o';
    if (isImage(mt)) return 'fa fa-file-image-o';
    return 'fa fa-file-o';
}

export function toggleMessageDropdown(msg) {
    // Đóng tất cả các dropdown khác
    this.state.currentThread.forEach(m => {
        m.showDropdown = (m.id === msg.id) ? !m.showDropdown : false;
    });
    this.render();

    // Nếu vừa mở dropdown, đăng ký sự kiện click ngoài
    if (msg.showDropdown) {
        setTimeout(() => {
            document.addEventListener("click", this._onClickOutsideDropdown);
        }, 0);
    }
}

export function onClickOutsideDropdown(ev) {
    const isInside = ev.target.closest(".dropdown-message-actions") || ev.target.closest(".icon-btn.more-btn");
    if (!isInside && this.state.currentThread?.some(m => m.showDropdown)) {
        this.state.currentThread.forEach(m => m.showDropdown = false);
        this.render();
    }
}

export function onFileSelected(event) {
    const files = event.target.files;
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        this.state.attachments.push({
            name: file.name,
            size: file.size,
            sizeText: formatFileSize(file.size),
            fileObj: file,
        });
    }
    console.log("📂 Attachments:", this.state.attachments);
    this.render();
}

function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes/1024).toFixed(0)}K`;
    return `${(bytes/1024/1024).toFixed(1)}M`;
}

export function removeAttachment(file) {
    this.state.attachments = this.state.attachments.filter(f => f !== file);
    this.render();
}

export function showSnoozeMenu(ev) {
    ev?.stopPropagation();
    this.state.showSnoozeMenu = true;
    console.log("showSnoozeMenu:", this.state.showSnoozeMenu);
    setTimeout(() => {
        document.addEventListener("click", this.boundCloseSnoozeMenu);
    }, 0);

}

export function closeSnoozeMenu(ev) {
    if (ev && ev.target.closest(".snooze-menu")) return;
    this.state.showSnoozeMenu = false;
    console.log("closeSnoozeMenu");
    document.removeEventListener("click", this.boundCloseSnoozeMenu);
}


export function openSnoozePopup() {
    this.state.showSnoozePopup = true;
    this.state.showSnoozeMenu = false;
    this.render();
}

export function closeSnoozePopup() {
    this.state.showSnoozePopup = false;
    this.render();
}

export function quickSnooze(option) {
    console.log("✅ Quick snooze for:", option);
    this.state.showSnoozeMenu = false;
    this.onSnooze({ option });  // đúng format
}


export function saveSnoozeDatetime() {
    console.log("✅ Snoozed until:", this.state.snoozeDate, this.state.snoozeTime);
    this.state.showSnoozePopup = false;
    this.onSnooze({
        snoozeDate: this.state.snoozeDate,
        snoozeTime: this.state.snoozeTime
    });
    // gọi function onSnooze đã tách riêng
}

export function toggleDropdown(ev) {
    ev.stopPropagation();
    this.state.showDropdown = !this.state.showDropdown;
    this.render();
    if (this.state.showDropdown) {
        document.addEventListener("click", this.closeDropdown);
    }
}

export function closeDropdown(ev) {
    if (!ev.target.closest(".dropdown-menu-caret") && !ev.target.closest(".icon-btn-option")) {
        this.state.showDropdown = false;
        this.render();
        document.removeEventListener("click", this.closeDropdown);
    }
}

export function toggleDropdownVertical() {
    this.state.showDropdownVertical = !this.state.showDropdownVertical;

    if (this.state.showDropdownVertical) {
        setTimeout(() => {
            document.addEventListener("click", this._onClickOutsideVertical);
        }, 0);
    } else {
        document.removeEventListener("click", this._onClickOutsideVertical);
    }

    this.render();
}

export function toggleAccounts() {
    this.state.showAccounts = !this.state.showAccounts;
}

export function toggleDropdownAccount() {
    this.state.showAccountDropdown = !this.state.showAccountDropdown;
}

export function toggleSelectAll(ev) {
    const isChecked = ev.target.checked;
    this.state.messages.forEach(msg => {
        msg.selected = isChecked;
    });
    this.render();
}
export function toggleSelect(msg) {
    msg.selected = !msg.selected;
    this.render();
}
export function toggleThreadMessage(threadMsg) {
    if (threadMsg) {
        threadMsg.collapsed = !threadMsg.collapsed;
        this.render();
    }
}



export function getStatusText(status) {
    switch (status) {
        case 'expired': return 'Session expired';
        case 'signed-out': return 'Signed out';
        default: return '';
    }
}

export function getInitialColor(initial) {
    const colors = {
        'R': '#5f6368',
        'V': '#1a73e8',
        'T': '#9c27b0',
        'W': '#673ab7'
    };
    return colors[initial] || '#5f6368';
}

export function getInitialBgColor(initial) {
    const colors = {
        'R': '#e8eaed',
        'V': '#e8f0fe',
        'T': '#f3e5f5',
        'W': '#ede7f6'
    };
    return colors[initial] || '#e8eaed';
}
export async function onCloseCompose() {
    const to = document.querySelector('.compose-input.to')?.value.trim() || '';
    const subject = document.querySelector('.compose-input.subject')?.value.trim() || '';
    const editor = this.editorInstance || window.editorInstance;
    const body = editor
        ? editor.getData()
        : document.querySelector('#compose_body')?.value || '';
    const hasContent = to || subject || body;
    const composeData = this.state.composeData || {};
    if (hasContent && this.state.activeTabId && !composeData.draft_id && !composeData.isSaving) {
        try {
            console.log('[Compose] Auto saving draft...');
            composeData.isSaving = true;
            const account = this.state.accounts.find(acc => acc.id === this.state.activeTabId) || {};
            const provider = account.type === 'outlook' ? 'outlook' : 'gmail';
            const resp = await fetch('/api/save_draft', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({
                    to,
                    subject,
                    body_html: body,
                    thread_id: composeData.thread_id || null,
                    message_id: composeData.message_id || null,
                    account_id: this.state.activeTabId,
                    provider,
                    draft_id: composeData.draft_id || null,
                }),
            });
            const data = await resp.json();
            console.log('[Compose] save_draft response', data);
            if (data.status === 'success') {
                composeData.draft_id = data.draft_id;
            }
            if (data.status === 'success' && this.state.currentFolder === 'drafts') {
                const activeEmail = this.state.accounts.find(acc => acc.id === this.state.activeTabId)?.email;
                if (activeEmail) {
                    await this.loadMessages(activeEmail, true);
                }
            }
            composeData.isSaving = false;
        } catch (err) {
            console.error('Failed to save draft', err);
            composeData.isSaving = false;
        }
    } else if (composeData.draft_id || composeData.isSaving) {
        console.log('[Compose] Draft already saved, skip auto save:', composeData.draft_id);
    }
    this.state.showComposeModal = false;
    if (editor) {
        editor.destroy();
        this.editorInstance = null;
        if (window.editorInstance === editor) {
            window.editorInstance = null;
        }
    }
}

export async function onSaveDraft() {
    const to = document.querySelector('.compose-input.to')?.value.trim() || '';
    const subject = document.querySelector('.compose-input.subject')?.value.trim() || '';
    const editor = this.editorInstance || window.editorInstance;
    const body = editor
        ? editor.getData()
        : document.querySelector('#compose_body')?.value || '';
    const hasContent = to || subject || body;
    if (hasContent && this.state.activeTabId) {
        const composeData = this.state.composeData || {};
        if (composeData.draft_id || composeData.isSaving) {
            console.log('[Compose] Draft already saved, skip manual save:', composeData.draft_id);
            return;
        }
        try {
            console.log('[Compose] Manual save draft');
            composeData.isSaving = true;
            const account = this.state.accounts.find(acc => acc.id === this.state.activeTabId) || {};
            const provider = account.type === 'outlook' ? 'outlook' : 'gmail';
            const resp = await fetch('/api/save_draft', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({
                    to,
                    subject,
                    body_html: body,
                    thread_id: composeData.thread_id || null,
                    message_id: composeData.message_id || null,
                    account_id: this.state.activeTabId,
                    provider,
                    draft_id: composeData.draft_id || null,
                }),
            });
            const data = await resp.json();
            console.log('[Compose] save_draft response', data);
            if (data.status === 'success') {
                composeData.draft_id = data.draft_id;
            }
            if (data.status === 'success' && this.state.currentFolder === 'drafts') {
                const activeEmail = this.state.accounts.find(acc => acc.id === this.state.activeTabId)?.email;
                if (activeEmail) {
                    await this.loadMessages(activeEmail, true);
                }
            }
            composeData.isSaving = false;
        } catch (err) {
            console.error('Failed to save draft', err);
            composeData.isSaving = false;
        }
    }
}
export function openFilePreview(ev) {
    const link = ev.currentTarget;
    const url = link.getAttribute("data-url");
    const modal = document.getElementById("filePreviewModal");
    const iframe = document.getElementById("filePreviewFrame");

    // Đảm bảo không có ?download=true ở URL
    iframe.src = url; // hoặc `${url}?inline=1`
    modal.style.display = "block";
}
export function toggleShowAllFolders() {
    this.state.showAllFolders = !this.state.showAllFolders;
    this.render();
}


