import logging
import re
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class MailingContact(models.Model):
    _inherit = "mailing.contact"

    partner_id = fields.Many2one("res.partner", string="Linked Partner")

    @api.model_create_multi
    def create(self, vals_list):
        contacts = super().create(vals_list)
        contacts.sudo()._ensure_partner_links()
        return contacts

    def write(self, vals):
        res = super().write(vals)
        if "email" in vals or "company_name" in vals:
            self.sudo()._ensure_partner_links()
        return res

    def _ensure_partner_links(self):
        for contact in self:
            if not contact.email:
                continue

            domain_match = re.search(r"@([\w\-\.]+)", contact.email)
            if not domain_match:
                continue

            domain = domain_match.group(1).lower()
            company_name = (contact.company_name or domain.split(".")[0]).strip()

            # 1. Tìm công ty active theo domain
            company = (
                self.env["res.company"]
                .sudo()
                .search(
                    [
                        ("x_domain_email", "=", domain),
                        ("active", "=", True),
                    ],
                    limit=1,
                )
            )

            # 2. Nếu chưa tìm được, tìm theo tên công ty gần đúng (ưu tiên công ty do bạn tạo tay)
            if not company:
                # Tìm partner công ty đã có tên gần đúng và email thuộc domain
                candidate_partners = (
                    self.env["res.partner"]
                    .sudo()
                    .search(
                        [
                            ("is_company", "=", True),
                            ("name", "=ilike", company_name),
                            ("email", "ilike", f"@{domain}"),
                        ],
                        limit=1,
                    )
                )

                if candidate_partners:
                    # Tìm công ty nào đang dùng partner này làm partner_id
                    company = (
                        self.env["res.company"]
                        .sudo()
                        .search(
                            [
                                ("partner_id", "=", candidate_partners.id),
                                ("active", "=", True),
                            ],
                            limit=1,
                        )
                    )

            # 3. Nếu vẫn không có, tạo mới công ty
            if not company:
                company = (
                    self.env["res.company"]
                    .sudo()
                    .create(
                        {
                            "name": company_name,
                            "x_domain_email": domain,
                        }
                    )
                )

            # 4. Cập nhật domain nếu thiếu
            if company and not company.x_domain_email:
                company.sudo().write({"x_domain_email": domain})

            # 5. Tạo hoặc liên kết partner công ty
            company_partner = company.partner_id
            if not company_partner:
                company_partner = (
                    self.env["res.partner"]
                    .sudo()
                    .create(
                        {
                            "name": company.name,
                            "is_company": True,
                            "email": f"info@{domain}",
                        }
                    )
                )
                company.sudo().write({"partner_id": company_partner.id})

            # 6. Tìm hoặc tạo partner cá nhân (contact)
            partner = (
                self.env["res.partner"]
                .sudo()
                .search([("email", "=", contact.email)], limit=1)
            )

            if not partner:
                partner = (
                    self.env["res.partner"]
                    .sudo()
                    .create(
                        {
                            "name": contact.name or contact.email.split("@")[0],
                            "email": contact.email,
                            "parent_id": company_partner.id,
                        }
                    )
                )

            if not contact.partner_id:
                contact.sudo().write({"partner_id": partner.id})


class ResCompany(models.Model):
    _inherit = "res.company"

    x_domain_email = fields.Char(
        string="Domain Email", help="Company domain extracted from contact emails"
    )

    @api.model
    def update_company_domains():
        # Lọc cả False, '', chuỗi trắng
        company_ids = models.execute_kw(
            db,
            uid,
            password,
            "res.company",
            "search",
            [[("x_domain_email", "in", [False, "", " "])]],
        )

        print(f"🔍 Tìm thấy {len(company_ids)} công ty chưa có x_domain_email.")

        if not company_ids:
            return

        companies = models.execute_kw(
            db,
            uid,
            password,
            "res.company",
            "read",
            [company_ids],
            {"fields": ["id", "name", "partner_id", "website"]},
        )

        partner_ids = [c["partner_id"][0] for c in companies if c["partner_id"]]
        partner_emails = {}
        if partner_ids:
            partners = models.execute_kw(
                db,
                uid,
                password,
                "res.partner",
                "read",
                [partner_ids],
                {"fields": ["id", "email"]},
            )
            partner_emails = {p["id"]: p["email"] for p in partners}

        updated = 0
        for comp in companies:
            partner_email = (
                partner_emails.get(comp["partner_id"][0])
                if comp["partner_id"]
                else None
            )
            domain = extract_domain_from_email(
                partner_email
            ) or extract_domain_from_website(comp["website"])

            if domain:
                models.execute_kw(
                    db,
                    uid,
                    password,
                    "res.company",
                    "write",
                    [[comp["id"]], {"x_domain_email": domain}],
                )
                print(f"✅ Gán domain `{domain}` cho công ty `{comp['name']}`")
                updated += 1
            else:
                print(f"⚠️ Không tìm được domain cho công ty `{comp['name']}`")

        print(f"✅ Hoàn tất cập nhật {updated}/{len(companies)} công ty.")

