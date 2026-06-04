from odoo import models


class ContratoEspecificoFacturarSeleccionWizardExtend(models.TransientModel):
    _inherit = "contrato.especifico.facturar.seleccion.wizard"

    def action_confirm(self) -> dict:
        lines_ordered = self.line_ids.filtered(
            lambda ln: not ln.invoiced and not ln.is_invoice_line
        )
        result = super().action_confirm()
        move_id = result.get("res_id")
        if move_id and lines_ordered:
            move = self.env["account.move"].browse(move_id)
            product_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == "product"
            )
            for inv_line, svc_line in zip(product_lines, lines_ordered):
                inv_line.with_context(check_move_validity=False).write(
                    {"service_line_id": svc_line.id}
                )
        return result
