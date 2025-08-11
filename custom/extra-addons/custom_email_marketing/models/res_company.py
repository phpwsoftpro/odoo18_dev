from odoo import models, _
from odoo.exceptions import UserError
import re


class ResPartner(models.Model):
    _inherit = "res.partner"

    def action_delete_if_allowed(self):
        not_deleted = []
        env = self.env
        MAX_ERRORS = 5
        MAX_RECORDS_PER_MODEL = 3

        def _find_usage(partner):
            details = []
            related_models = {
                "account.move": {
                    "field": "partner_id",
                    "label": "Hóa đơn",
                    "fields_to_show": ["name", "invoice_date"],
                },
                "account.payment": {
                    "field": "partner_id",
                    "label": "Thanh toán",
                    "fields_to_show": ["name", "payment_date"],
                },
                "account.move.line": {
                    "field": "partner_id",
                    "label": "Dòng bút toán",
                    "fields_to_show": ["name"],
                },
                "sale.order": {
                    "field": "partner_id",
                    "label": "Đơn bán",
                    "fields_to_show": ["name", "date_order"],
                },
                "purchase.order": {
                    "field": "partner_id",
                    "label": "Đơn mua",
                    "fields_to_show": ["name", "date_order"],
                },
                "calendar.filter": {
                    "field": "partner_id",
                    "label": "Bộ lọc lịch",
                    "fields_to_show": ["name"],
                },
                "res.users": {
                    "field": "partner_id",
                    "label": "Người dùng",
                    "fields_to_show": ["name", "login"],
                },
                "res.company": {
                    "field": "partner_id",
                    "label": "Công ty",
                    "fields_to_show": ["name"],
                },
            }

            for model_name, info in related_models.items():
                try:
                    model = env[model_name]
                except KeyError:
                    continue
                domain = [(info["field"], "=", partner.id)]
                records = model.with_context(active_test=False).search(
                    domain, limit=MAX_RECORDS_PER_MODEL + 1
                )
                if records:
                    display_list = []
                    for rec in records[:MAX_RECORDS_PER_MODEL]:
                        summary = ", ".join(
                            f"{field}: {getattr(rec, field, '') or ''}"
                            for field in info["fields_to_show"]
                        )
                        display_list.append(f"[{summary}]")
                    extra = "…" if len(records) > MAX_RECORDS_PER_MODEL else ""
                    details.append(
                        f"{info['label']} ({len(records)}): "
                        + ", ".join(display_list)
                        + extra
                    )
            return details

        def _parse_constraint_error(exc_msg):
            """Phân tích lỗi khóa ngoại để mô tả rõ ràng hơn bằng tiếng Việt."""
            table_labels = {
                "calendar_filters": "Bộ lọc lịch",
                "res_company": "Công ty",
                "res_users": "Người dùng",
                "account_move": "Hóa đơn",
                "account_payment": "Thanh toán",
                "sale_order": "Đơn bán",
                "purchase_order": "Đơn mua",
                "account_move_line": "Dòng bút toán",
            }

            matches = re.findall(
                r'violates foreign key constraint "(.*?)" on table "(.*?)"', exc_msg
            )
            results = []
            for constraint, table in matches:
                label = table_labels.get(table, table.replace("_", " ").capitalize())
                results.append(f"Liên quan đến {label} (ràng buộc: {constraint})")
            return results

        for partner in self:
            partner_name = partner.display_name or partner.name or f"ID {partner.id}"
            try:
                with env.cr.savepoint():
                    partner.unlink()
            except Exception as e:
                used_in = _find_usage(partner)
                if not used_in:
                    parsed = _parse_constraint_error(str(e))
                    used_in = parsed if parsed else [str(e).splitlines()[0]]
                msg = f"- {partner_name}: đang được dùng ở:\n  - " + "\n  - ".join(
                    used_in
                )
                not_deleted.append(msg)

        if not_deleted:
            truncated = not_deleted[:MAX_ERRORS]
            more_count = len(not_deleted) - MAX_ERRORS
            msg = _("Không thể xóa các đối tượng sau:\n\n%s") % "\n\n".join(truncated)
            if more_count > 0:
                msg += _("\n\n…và còn %s bản ghi khác không thể xóa.") % more_count
            raise UserError(msg)
