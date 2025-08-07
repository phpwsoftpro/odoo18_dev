from odoo import models, fields, api

class MoveTaskWizard(models.TransientModel):
    _name = 'move.task.wizard'
    _description = 'Move Task to Another Project'

    task_id = fields.Many2one('project.task', string="Task", required=True)
    new_project_id = fields.Many2one('project.project', string="New Project", required=True)
    new_stage_id = fields.Many2one('project.task.type', string="New Stage", required=True, domain="[('project_ids', '=', new_project_id)]")

    @api.onchange('new_project_id')
    def _onchange_new_project_id(self):
        """ Khi chọn project mới, chỉ hiển thị các stage thuộc project đó """
        if self.new_project_id:
            return {'domain': {'new_stage_id': [('project_ids', '=', self.new_project_id.id)]}}

    def move_task(self):
        """ Cập nhật project và stage của task """
        if self.new_project_id and self.new_stage_id:
            self.task_id.write({
                'project_id': self.new_project_id.id,
                'stage_id': self.new_stage_id.id
            })
