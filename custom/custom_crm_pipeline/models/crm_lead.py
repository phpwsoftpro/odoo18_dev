from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TechStack(models.Model):
    _name = "tech.stack"
    _description = "Technology Stack"

    name = fields.Char(string="Technology Name", required=True)


class ProjectType(models.Model):
    _name = "project.type"
    _description = "Project Type"

    name = fields.Char(string="Project Type", required=True)


class CrmLead(models.Model):
    _inherit = "crm.lead"

    project_type_id = fields.Many2one(
        comodel_name="project.type", string="Project Type"
    )

    tech_stack_ids = fields.Many2many(
        comodel_name="tech.stack",
        string="Tech Stack",
    )
    start_date = fields.Date(string="Expected Start Date")
    end_date = fields.Date(string="Expected End Date")
    project_duration = fields.Char(
        string="Project Duration", compute="_compute_project_duration"
    )

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for lead in self:
            if lead.start_date and lead.end_date and lead.end_date < lead.start_date:
                raise ValidationError("Expected End Date phải sau Expected Start Date.")

    @api.depends("start_date", "end_date")
    def _compute_project_duration(self):
        config_unit = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("crm_lead.project_duration_unit", "days")
        )
        for lead in self:
            duration = ""
            if lead.start_date and lead.end_date:
                delta = (lead.end_date - lead.start_date).days
                if config_unit == "weeks":
                    duration = f"{round(delta / 7)} weeks"
                else:
                    duration = f"{delta} days"
            lead.project_duration = duration
