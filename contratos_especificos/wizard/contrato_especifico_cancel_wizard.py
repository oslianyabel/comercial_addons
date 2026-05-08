from odoo import fields, models


class ContratoEspecificoCancel(models.TransientModel):
    _name = "contrato.especifico.cancel.wizard"
    _description = "Wizard de Cancelación de Contrato Específico"

    contrato_id = fields.Many2one("contrato.especifico", required=True, readonly=True)
    motivo = fields.Text(string="Motivo de Cancelación", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.contrato_id.action_cancel_confirmed(self.motivo)
        return {"type": "ir.actions.act_window_close"}
