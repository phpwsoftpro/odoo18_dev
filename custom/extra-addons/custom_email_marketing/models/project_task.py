from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
from pathlib import Path
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class HrJob(models.Model):
    _inherit = "hr.job"

    # --- new fields ---
    alias_name = fields.Char(copy=False)
    assignee_ids = fields.Many2many(
        "res.users", "hr_job_assignee_rel", "job_id", "user_id", string="Assignees"
    )
    deadline = fields.Date(string="Deadline")
    crm_task_id = fields.Many2one(
        'project.task',
        string='CRM Task',
        help='Task từ CRM gắn với vị trí này',
        domain="[('project_id.privacy_visibility', '!=', 'portal')]",
        ondelete='set null'
    )
    crm_task_ids = fields.Many2many(
    "project.task",
    "job_crm_task_rel",
    "job_id",
    "task_id",
    string="CRM Tasks"
    )

    has_crm_task = fields.Boolean(compute="_compute_has_crm_task")
    job_details = fields.Html(string="Job Details")

    # --- computes ---
    is_overdue = fields.Boolean(compute="_compute_is_overdue")
    application_count = fields.Integer(compute="_compute_application_count")

    # ----------------------------------------------------
    #  COMPUTE METHODS
    # ----------------------------------------------------
    @api.depends("deadline")
    def _compute_is_overdue(self):
        today = date.today()
        for rec in self:
            rec.is_overdue = bool(rec.deadline and rec.deadline < today)

    @api.depends("crm_task_id")
    def _compute_has_crm_task(self):
        for rec in self:
            rec.has_crm_task = bool(rec.crm_task_id)

   

    # ----------------------------------------------------
    #  ONCHANGE
    # ----------------------------------------------------
    @api.onchange("department_id")
    def _onchange_department_id(self):
        if self.department_id:
            employees = self.env["hr.employee"].search(
                [("department_id", "=", self.department_id.id)]
            )
            return {
                "domain": {
                    "assignee_ids": [("id", "in", employees.mapped("user_id").ids)]
                }
            }

    # ----------------------------------------------------
    #  ACTION
    # ----------------------------------------------------
    def action_open_crm_task(self):
        """Open linked project.task in a modal."""
        self.ensure_one()
        if not self.crm_task_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": self.crm_task_id.display_name,
            "res_model": "project.task",
            "res_id": self.crm_task_id.id,
            "view_mode": "form",
            "view_id": self.env.ref("project.view_task_form2").id,
            "target": "new",
        }
    def action_open_in_popup(self):
        self.ensure_one()
        if not self.crm_task_id:
            raise UserError("No CRM task linked.")
        return {
            "name": self.crm_task_id.name,
            "type": "ir.actions.act_window",
            "res_model": "project.task",
            "res_id": self.crm_task_id.id,
            "view_mode": "form",
            "target": "new",
    }
    all_crm_tasks = fields.Many2many(
        "project.task",
        compute="_compute_all_crm_tasks",
        string="All CRM Tasks",
        store=False  # không cần lưu DB
    )

    @api.depends('crm_task_id', 'crm_task_ids')
    def _compute_all_crm_tasks(self):
        for job in self:
            all_tasks = job.crm_task_ids
            if job.crm_task_id and job.crm_task_id not in all_tasks:
                all_tasks |= job.crm_task_id
            job.all_crm_tasks = all_tasks
    



class ProjectTask(models.Model):
    _inherit = "project.task"

    start_date = fields.Datetime(string="Start Date",default=lambda self: datetime.now())

    start_date_now = fields.Datetime(string="Start Date Now")
    # start_date_n = fields.Datetime(string="Start Date Now")

    deepseek_text = fields.Text(string="Text DeepSeek")
    # deepseek_text = fields.Html("Text DeepSeek", default='', sanitize_style=True)
    email_to = fields.Char(string="Email To")
    sender_name = fields.Char(string="Sender Name")

    remaining_days = fields.Char(
        string="Remaining Time", compute="_compute_remaining_days"
    )
    priority = fields.Selection(
        [("0", "Low"), ("1", "Medium"), ("2", "High")], string="Priority", default="1"
    )
    has_new_log = fields.Boolean(string="New Log Note", default=False)
    new_log_count = fields.Integer(string="New Log Note Count", default=0)
    connected_task_ids = fields.Many2many(
        "project.task",
        "project_task_connection_rel",
        "task_id",
        "connected_task_id",
        string="Connected Tasks",
    )
    cover_image = fields.Binary("Cover Image")



    @api.onchange("start_date")
    def _onchange_start_date(self):
        if (
            self.start_date
            and self.date_deadline
            and self.start_date > self.date_deadline
        ):
            self.start_date = self.date_deadline - timedelta(days=1)

    @api.onchange("date_deadline")
    def _onchange_date_deadline(self):
        if (
            self.start_date
            and self.date_deadline
            and self.start_date > self.date_deadline
        ):
            self.start_date = self.date_deadline - timedelta(days=1)

    @api.model
    def create(self, vals):
        record = super(ProjectTask, self).create(vals)
        if "cover_image" in vals and vals.get("cover_image"):
            attachment = self.env["ir.attachment"].browse(vals["cover_image"])
            if attachment.exists():
                record.message_post(
                    body="Cover image set", attachment_ids=[(4, attachment.id)]
                )
        return record

    def write(self, vals):
        result = super(ProjectTask, self).write(vals)
        for record in self:
            if "cover_image" in vals and vals.get("cover_image"):
                attachment = self.env["ir.attachment"].browse(vals["cover_image"])
                if attachment.exists():
                    record.message_post(
                        body="Cover image updated", attachment_ids=[(4, attachment.id)]
                    )
        return result

    @api.depends("date_deadline")
    def _compute_remaining_days(self):
        for task in self:
            if task.date_deadline:
                # Chuyển đổi deadline sang datetime với timezone của hệ thống
                deadline = fields.Datetime.to_datetime(task.date_deadline)

                # Chuyển deadline sang timezone của user
                deadline = fields.Datetime.context_timestamp(task, deadline)

                # Lấy thời gian hiện tại theo timezone của user
                now = fields.Datetime.context_timestamp(task, fields.Datetime.now())

                # Tính khoảng cách thời gian
                remaining = deadline - now

                # Format lại hiển thị
                task.remaining_days = (
                    f"{remaining.days} days → {deadline.strftime('%I:%M%p %d/%m/%Y')}"
                )
            else:
                task.remaining_days = "No Deadline"

    def action_move_to_project(self):
        return {
            "name": "Move Task to Another Project",
            "type": "ir.actions.act_window",
            "res_model": "move.task.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_task_id": self.id},
        }

    def message_post(self, **kwargs):
        """Override message_post to track new log notes"""
        message = super(ProjectTask, self).message_post(**kwargs)

        # Check if this is a note (not a regular comment)
        if (
            kwargs.get("message_type") == "comment"
            and kwargs.get("subtype_xmlid") == "mail.mt_note"
        ):

            # Update counter for other users
            other_users = self.message_follower_ids.mapped(
                "partner_id.user_ids"
            ).filtered(lambda u: u.id != self.env.user.id)

            if other_users:
                self.sudo().write(
                    {"has_new_log": True, "new_log_count": self.new_log_count + 1}
                )

        if message and message.attachment_ids:
            # Filter to get only image attachments
            image_attachments = message.attachment_ids.filtered(
                lambda a: a.mimetype and a.mimetype.startswith("image/")
            )

            # Make sure we have at least one image
            if image_attachments and not self.cover_image:
                # Get the first image attachment only
                first_image = image_attachments[0]

                # Try different field names that might be used for the Kanban card image
                try:
                    # Option 1: displayed_image_id (Odoo 14+)
                    if hasattr(self, "displayed_image_id"):
                        self.sudo().write({"displayed_image_id": first_image.id})

                    # Option 2: kanban_image (some custom implementations)
                    elif hasattr(self, "kanban_image"):
                        self.sudo().write({"kanban_image": first_image.id})

                    # Option 3: cover_image as a binary field
                    elif hasattr(self, "cover_image"):
                        self.sudo().write({"cover_image": first_image.datas})

                    # Option 4: For Odoo 15+, preview_image field
                    elif hasattr(self, "preview_image"):
                        self.sudo().write({"preview_image": first_image.datas})
                except Exception as e:
                    _logger.error("Error setting task image: %s", str(e))
        return message

    def action_view_task(self):
        """Action to view task and reset notification"""
        self.ensure_one()
        # Reset notification state
        self.write({"has_new_log": False, "new_log_count": 0})

        # Return form view action
        return {
            "name": self.name,
            "type": "ir.actions.act_window",
            "res_model": "project.task",
            "res_id": self.id,
            "view_mode": "form",
            "view_type": "form",
            "target": "current",
        }

    def action_reply_email(self):
        """Mở form nhập nội dung và Message-ID khi reply email"""
        wizard_model = self.env["send.task.email.wizard"]  # Import gián tiếp
        return {
            "type": "ir.actions.act_window",
            "name": "Reply Email",
            "res_model": wizard_model._name,  # Sử dụng model name từ Odoo ORM
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_email_to": self.partner_id.email,  # Điền email khách hàng
            },
        }

    def action_open_in_new_tab(self):
        """Open the task in a new tab using client action"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/web#id=%d&model=project.task&view_type=form" % self.id,
            "target": "new",
        }
    def action_open_in_popup(self):
        self.ensure_one()
        view = self.env.ref('project.view_task_form2')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'view_id': view.id,  # ⬅️ Thêm dòng này
            'views': [(view.id, 'form')],
        }


