from odoo import _, fields, models
from odoo.exceptions import UserError


class ContratoEspecificoFacturarTodoWizard(models.TransientModel):
    _name = "contrato.especifico.facturar.todo.wizard"
    _description = "Wizard de Departamento para Facturar Todo"

    contrato_id = fields.Many2one(
        "contrato.especifico",
        string="Contrato Específico",
        readonly=True,
        required=True,
    )
    departamento_id = fields.Many2one(
        "res.partner.departamento",
        string="Departamento",
    )

    def action_confirm(self) -> dict:
        """Crea una única factura con una línea por cada línea de servicio pendiente."""
        self.ensure_one()

        contract = self.contrato_id
        if not contract:
            raise UserError(_("No hay contrato asociado."))

        uninvoiced_lines = contract.line_ids.filtered(
            lambda ln: not ln.invoiced and not ln.is_invoice_line
        )
        uninvoiced_ueb_lines = contract.ueb_section_ids.mapped("line_ids").filtered(
            lambda ln: not ln.invoiced and not ln.is_invoice_line
        )

        all_lines = list(uninvoiced_lines) + list(uninvoiced_ueb_lines)
        if not all_lines:
            raise UserError(_("Todas las líneas de servicio ya han sido facturadas."))

        # Preparar fechas en todas las líneas
        for line in all_lines:
            line._apply_default_invoice_dates()

        # Construir las líneas de factura
        invoice_line_ids = []
        for line in all_lines:
            invoice_line_ids.append((
                0, 0,
                {
                    "product_id": line.product_id.id,
                    "name": line.name,
                    "quantity": line.quantity,
                    "product_uom_id": line.uom_id.id,
                    "price_unit": line.price_unit,
                },
            ))

        partner = contract.partner_id
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_date": fields.Date.today(),
            "contrato_especifico_id": contract.id,
            "invoice_payment_term_id": contract.forma_pago_id.id
            if contract.forma_pago_id
            else False,
            "departamento_id": self.departamento_id.id if self.departamento_id else False,
            "client_address": f"{partner.street or ''} {partner.city or ''}".strip(),
            "client_nit": getattr(partner, "tax_id", None) or partner.vat or "",
            "client_bank_account": getattr(partner, "bank_account_cup", None) or "",
            "realizada_por_id": contract.realizada_por_id.id
            if contract.realizada_por_id
            else False,
            "invoice_line_ids": invoice_line_ids,
        })

        # Marcar todas las líneas como facturadas
        uninvoiced_lines.with_context(is_uninvoice=True).write({"invoiced": True})
        uninvoiced_ueb_lines.with_context(is_uninvoice=True).write({"invoiced": True})

        return {
            "name": _("Factura"),
            "view_mode": "form",
            "res_model": "account.move",
            "res_id": move.id,
            "type": "ir.actions.act_window",
        }
