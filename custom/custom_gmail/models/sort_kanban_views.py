from odoo import models, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model
    def get_sorted_ids_by_deadline(self, group_id):
        domain = [('stage_id', '=', group_id)]
        tasks = self.search(domain, order='date_deadline asc')
        return tasks.ids
