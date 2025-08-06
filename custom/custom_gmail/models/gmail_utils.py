import logging
from datetime import datetime
import pytz
from odoo import models, api

_logger = logging.getLogger(__name__)


class GmailUtils(models.Model):
    _inherit = "mail.message"

    def parse_date(self, raw_date):
        """
        Attempt to parse a date string with multiple known formats.
        """
        cleaned_date = raw_date.split("(")[0].strip()

        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%d %b %Y %H:%M:%S %z",
            "%d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S GMT",
        ]

        for fmt in formats:
            try:
                parsed_date = datetime.strptime(cleaned_date, fmt)
                if not parsed_date.tzinfo:
                    parsed_date = pytz.utc.localize(parsed_date)
                return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

        _logger.error("Failed to parse date: %s. Tried formats: %s", raw_date, formats)
        return None
