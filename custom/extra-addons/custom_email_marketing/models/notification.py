import logging
from odoo import models, api


class ProjectTask(models.Model):
    _inherit = "project.task"

    @api.model
    def get_project_notifications(self):
        partner_id = self.env.user.partner_id.id
        notifications = []

        # _logger.info(f"Fetching notifications for partner_id: {partner_id}")

        # Get notifications related to project.task from mail.notification
        notif_records = (
            self.env["mail.notification"]
            .sudo()
            .search(
                [("res_partner_id", "=", partner_id)],
                order="date desc",  # Use the 'date' field in mail.notification if it exists
                limit=50,
            )
        )

        # _logger.info(f"Found {len(notif_records)} notifications for partner_id: {partner_id}")

        for notif in notif_records:
            msg = notif.mail_message_id
            if msg:
                notifications.append(
                    {
                        "id": msg.id,
                        "body": msg.body,
                        "subject": msg.subject or "(No Subject)",
                        "author": msg.author_id.name or "Unknown",
                        "date": (
                            msg.date.strftime("%Y-%m-%d %H:%M:%S")
                            if msg.date
                            else "Unknown"
                        ),
                        "model": msg.model,
                        "res_id": msg.res_id,
                        "task_name": (
                            self.env[msg.model].sudo().browse(msg.res_id).name
                            if msg.model == "project.task"
                            else ""
                        ),
                    }
                )

        # _logger.info(f"Returning {len(notifications)} notifications.")
        return notifications

    def _track_subtype(self, init_values):
        self.ensure_one()
        if "stage_id" in init_values:
            # _logger.info(
            #     f"Skipping notification for stage change for task: {self.name}"
            # )
            return False
        return super()._track_subtype(init_values)

    def _create_project_notification(self, subject, body):
        partner_ids = [u.partner_id.id for u in self.user_ids if u.partner_id]
        if not partner_ids:
            # _logger.warning(f"No partners found to notify for task: {self.name}")
            return

        # _logger.info(
        #     f"Creating notification for partners: {partner_ids} for task: {self.name}"
        # )

        msg = (
            self.env["mail.message"]
            .sudo()
            .create(
                {
                    "model": "project.task",
                    "res_id": self.id,
                    "message_type": "notification",
                    "subject": subject,
                    "body": body,
                    "author_id": self.env.user.partner_id.id,
                    "partner_ids": [(6, 0, partner_ids)],
                }
            )
        )

        # Create mail.notification manually to ensure all users see the notification
        for partner_id in partner_ids:
            self.env["mail.notification"].sudo().create(
                {
                    "mail_message_id": msg.id,
                    "res_partner_id": partner_id,
                    "notification_type": "inbox",
                    "is_read": False,
                }
            )

    def _send_stage_change_notification(self, from_stage, to_stage):
        body = f"<p><b>{self.name}</b> was moved from <b>{from_stage}</b> to <b>{to_stage}</b></p>"
        # _logger.info(
        #     f"Sending stage change notification for task: {self.name} from {from_stage} to {to_stage}"
        # )
        self._create_project_notification(f"Task moved: {self.name}", body)

    def _send_create_notification(self):
        body = f"<p>A new task <b>{self.name}</b> has been created in project <b>{self.project_id.name}</b>.</p>"
        # _logger.info(f"Sending creation notification for task: {self.name}")
        self._create_project_notification(f"New Task: {self.name}", body)

    def message_post(self, **kwargs):
        # _logger.info(f"Posting message for task: {self.name} with data: {kwargs}")
        res = super().message_post(**kwargs)

        if kwargs.get("message_type") == "comment":
            partner_ids = kwargs.get("partner_ids", [])
            notified_partner_ids = set(partner_ids)

            # Add assigned users to the task to the notification list
            for user in self.user_ids:
                notified_partner_ids.add(user.partner_id.id)

            # Get actual comment content
            comment_body = kwargs.get("body") or res.body

            # _logger.info(
            #     f"Creating comment notifications for task: {self.name} with comment: {comment_body}"
            # )

            # Create mail notification for each partner tagged in the comment
            for partner_id in notified_partner_ids:
                existing = (
                    self.env["mail.notification"]
                    .sudo()
                    .search(
                        [
                            ("mail_message_id", "=", res.id),
                            ("res_partner_id", "=", partner_id),
                        ],
                        limit=1,
                    )
                )

                if not existing:
                    # _logger.info(
                    #     f"Creating notification for partner: {partner_id} for comment on task: {self.name}"
                    # )
                    self.env["mail.notification"].sudo().create(
                        {
                            "mail_message_id": res.id,  # Link to the existing comment
                            "res_partner_id": partner_id,
                            "notification_type": "inbox",  # Ensure the notification goes to inbox
                            "is_read": False,
                        }
                    )

        return res

    @api.model
    def create(self, vals):
        # _logger.info(f"Creating task with values: {vals}")
        task = super().create(vals)
        task._send_create_notification()
        return task

    def write(self, vals):
        # _logger.info(f"Updating task {self.name} with values: {vals}")
        old_stages = {rec.id: rec.stage_id.name for rec in self}
        res = super().write(vals)
        if "stage_id" in vals:
            for rec in self:
                from_stage = old_stages.get(rec.id)
                to_stage = rec.stage_id.name
                if from_stage != to_stage:
                    # _logger.info(
                    #     f"Task {rec.name} moved from {from_stage} to {to_stage}"
                    # )
                    rec._send_stage_change_notification(from_stage, to_stage)
        return res
