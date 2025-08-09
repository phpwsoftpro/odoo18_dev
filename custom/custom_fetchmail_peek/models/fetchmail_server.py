from odoo import models
import imaplib
import logging

_logger = logging.getLogger(__name__)


class FetchmailServer(models.Model):
    _inherit = "fetchmail.server"

    def fetch_mail(self, raise_exception=True):
        """Override fetch_mail to use BODY.PEEK[] so emails remain unseen on IMAP."""
        additionnal_context = {"fetchmail_cron_running": True}
        MailThread = self.env["mail.thread"]
        for server in self:
            _logger.info(
                "start checking for new emails on %s server %s",
                server.server_type,
                server.name,
            )
            additionnal_context["default_fetchmail_server_id"] = server.id
            count, failed = 0, 0
            imap_server = None
            connection_type = server._get_connection_type()
            if connection_type == "imap":
                try:
                    imap_server = server.connect()
                    imap_server.select()
                    result, data = imap_server.search(None, "(UNSEEN)")
                    for num in data[0].split():
                        result, data = imap_server.fetch(num, "(BODY.PEEK[])")
                        try:
                            MailThread.with_context(
                                **additionnal_context
                            ).message_process(
                                server.object_id.model,
                                data[0][1],
                                save_original=server.original,
                                strip_attachments=(not server.attach),
                            )
                        except Exception:
                            _logger.info(
                                "Failed to process mail from %s server %s.",
                                server.server_type,
                                server.name,
                                exc_info=True,
                            )
                            failed += 1
                        self._cr.commit()
                        count += 1
                    _logger.info(
                        "Fetched %d email(s) on %s server %s; %d succeeded, %d failed.",
                        count,
                        server.server_type,
                        server.name,
                        (count - failed),
                        failed,
                    )
                except Exception as e:
                    if raise_exception:
                        raise models.ValidationError(
                            "Couldn't get your emails. Check out the error message below:\n%s"
                            % e
                        ) from e
                    else:
                        _logger.info(
                            "General failure when trying to fetch mail from %s server %s.",
                            server.server_type,
                            server.name,
                            exc_info=True,
                        )
                finally:
                    if imap_server:
                        try:
                            imap_server.close()
                            imap_server.logout()
                        except (OSError, imaplib.IMAP4.abort):
                            _logger.warning(
                                "Failed to properly finish imap connection: %s.",
                                server.name,
                                exc_info=True,
                            )
            else:
                # fallback POP3
                super(FetchmailServer, server).fetch_mail(
                    raise_exception=raise_exception
                )
            server.write({"date": self.env.fields.Datetime.now()})
        return True
