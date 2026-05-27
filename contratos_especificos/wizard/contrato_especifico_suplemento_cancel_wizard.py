from odoo import fields, models


class ContratoEspecificoSuplementoCancel(models.TransientModel):
    _name = "contrato.especifico.suplemento.cancel.wizard"
    _description = "Wizard de Cancelación de Suplemento de Contrato Específico"

    suplemento_id = fields.Many2one(
        "contrato.especifico.suplemento", required=True, readonly=True
    )
    motivo = fields.Text(string="Motivo de Cancelación", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.suplemento_id.action_cancel_confirmed(self.motivo)
        return {"type": "ir.actions.act_window_close"}
