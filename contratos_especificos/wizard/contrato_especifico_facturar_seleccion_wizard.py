from odoo import _, fields, models
from odoo.exceptions import UserError


class ContratoEspecificoFacturarSeleccionWizard(models.TransientModel):
    _name = "contrato.especifico.facturar.seleccion.wizard"
    _description = "Wizard de Facturación de Líneas Seleccionadas"

    contrato_id = fields.Many2one(
        "contrato.especifico",
        string="Contrato Específico",
        readonly=True,
        required=True,
    )
    line_ids = fields.Many2many(
        "contrato.especifico.line",
        relation="ce_fac_sel_wiz_line_rel",
        string="Líneas a Facturar",
        domain="[('contrato_id', '=', contrato_id), ('invoiced', '=', False), ('is_invoice_line', '=', False)]",
    )
    departamento_id = fields.Many2one(
        "res.partner.departamento",
        string="Departamento",
    )

    def action_confirm(self) -> dict:
        """Crea una única factura con todas las líneas seleccionadas."""
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_("Debe seleccionar al menos una línea de servicio a facturar."))

        lines = self.line_ids.filtered(lambda ln: not ln.invoiced and not ln.is_invoice_line)
        if not lines:
            raise UserError(_("Ninguna de las líneas seleccionadas está pendiente de facturar."))

        contract = self.contrato_id

        for line in lines:
            line._apply_default_invoice_dates()

        invoice_line_ids = [
            (0, 0, {
                "product_id": line.product_id.id,
                "name": line.name,
                "quantity": line.quantity,
                "product_uom_id": line.uom_id.id,
                "price_unit": line.price_unit,
            })
            for line in lines
        ]

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

        lines.with_context(is_uninvoice=True).write({"invoiced": True})

        return {
            "name": _("Factura"),
            "view_mode": "form",
            "res_model": "account.move",
            "res_id": move.id,
            "type": "ir.actions.act_window",
        }
