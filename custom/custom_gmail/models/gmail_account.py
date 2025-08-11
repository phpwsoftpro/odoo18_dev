from odoo import models, fields, api, SUPERUSER_ID
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging
import requests

_logger = logging.getLogger(__name__)


class GmailAccount(models.Model):
    _name = "gmail.account"
    _description = "Gmail Account"
    avatar_url = fields.Char("Avatar URL")
    user_id = fields.Many2one("res.users", string="User", required=True)
    gmail_authenticated_email = fields.Char(string="Authenticated Email")
    email = fields.Char(string="Email", required=True)
    gmail_authenticated_email = fields.Char(string="Authenticated Email")
    access_token = fields.Char("Access Token")
    refresh_token = fields.Char("Refresh Token")
    token_expiry = fields.Datetime("Token Expiry")
    has_new_mail = fields.Boolean("Has New Mail", default=False)
    provider = fields.Selection(
        [("gmail", "Gmail"), ("outlook", "Outlook")],
        string="Provider",
        required=False,
        default="gmail",
    )


class GmailAccountSyncState(models.Model):
    _name = "gmail.account.sync.state"
    _description = "Gmail Account Sync Metadata"
    _rec_name = "gmail_account_id"

    gmail_account_id = fields.Many2one(
        "gmail.account", required=True, ondelete="cascade", index=True
    )
    last_fetch_at = fields.Datetime(string="Last Fetched At")
    gmail_ids_30_days = fields.Text(string="Gmail IDs in 30 Days (JSON)")


class GmailAccountSession(models.Model):
    _name = "gmail.account.session"
    _description = "Active Gmail Tabs in UI"

    gmail_account_id = fields.Many2one(
        "gmail.account", required=True, ondelete="cascade"
    )
    user_id = fields.Many2one("res.users", required=True)
    last_ping = fields.Datetime("Last Ping Time", default=fields.Datetime.now)

    @api.model
    def prune_stale_sessions(self):
        """Xóa session đã không ping hơn 2 phút"""
        threshold = fields.Datetime.now() - timedelta(minutes=2)
        stale_sessions = self.search([("last_ping", "<", threshold)])
        if stale_sessions:
            _logger.info(f"🧹 Đã xóa {len(stale_sessions)} session cũ.")
            stale_sessions.unlink()


class GmailAccountCron(models.Model):
    _inherit = "gmail.account"

    @api.model
    def cron_fetch_gmail_accounts(self):
        """
        Cron fetch Gmail account đang mở UI, không dùng FOR UPDATE để tránh lỗi.
        """
        self.env["gmail.account.session"].prune_stale_sessions()

        self.env.cr.execute(
            """
            SELECT s.gmail_account_id
            FROM gmail_account_session s
            JOIN gmail_account g ON g.id = s.gmail_account_id
            WHERE g.access_token IS NOT NULL AND g.refresh_token IS NOT NULL
        """
        )
        account_ids = list({row[0] for row in self.env.cr.fetchall()})

        if not account_ids:
            # _logger.info("⏸ Không có Gmail account nào đang mở trên UI.")
            return

        for acc_id in account_ids:
            try:
                account = self.browse(acc_id)
                _logger.info(f"🔄 Cron: Fetch Gmail for {account.email}")
                self.env["mail.message"].fetch_gmail_for_account(account)
                self.env["mail.message"].fetch_gmail_sent_for_account(account)
                self.env["mail.message"].fetch_gmail_drafts_for_account(account)
            except Exception as e:
                _logger.warning(f"⚠️ Lỗi khi đồng bộ Gmail cho account {acc_id}: {e}")

    def refresh_access_token(self, account):
        config = self.env["mail.message"].sudo().get_google_config()
        if not account.refresh_token:
            _logger.error(f"❌ No refresh token for account {account.email}")
            return False

        payload = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "refresh_token": account.refresh_token,
            "grant_type": "refresh_token",
        }

        response = requests.post(config["token_uri"], data=payload)
        if response.status_code != 200:
            _logger.error(
                f"❌ Failed to refresh token for {account.email}: {response.text}"
            )
            return False

        tokens = response.json()
        access_token = tokens.get("access_token")
        expires_in = tokens.get("expires_in")

        if not access_token:
            _logger.error(
                f"❌ Không nhận được access_token từ phản hồi: {response.text}"
            )
            return False

        try:
            account.write(
                {
                    "access_token": access_token,
                    "token_expiry": fields.Datetime.to_string(
                        fields.Datetime.now() + timedelta(seconds=expires_in)
                    ),
                }
            )
            _logger.info(f"✅ Refreshed token for {account.email}")
            return True
        except Exception as e:
            _logger.warning(f"⚠️ Ghi access_token thất bại (xung đột ghi): {e}")
            return False


# 🎯 POST INIT HOOK: đổi gmail_account_id sang BIGINT nếu cần
def post_init_hook(cr, registry):
    cr.execute(
        """
        DO $$
        BEGIN
            -- Check and convert gmail_account_id to BIGINT if it's still INTEGER
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'gmail_account_session'
                AND column_name = 'gmail_account_id'
                AND data_type = 'integer'
            ) THEN
                RAISE NOTICE '🔧 Đang chuyển gmail_account_id → BIGINT...';
                ALTER TABLE gmail_account_session
                ALTER COLUMN gmail_account_id TYPE BIGINT;
                RAISE NOTICE '✅ Đã chuyển gmail_account_id → BIGINT thành công';
            ELSE
                RAISE NOTICE '👌 gmail_account_id đã là BIGINT, không cần đổi.';
            END IF;
        END$$;
    """
    )
