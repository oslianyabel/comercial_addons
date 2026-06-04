from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LineasPorFacturarMultiplesWizard(models.TransientModel):
    _name = "lineas.por.facturar.multiples.wizard"
    _description = "Wizard de Facturación de Múltiples Líneas"

    contrato_id = fields.Many2one(
        "contrato.especifico",
        string="Contrato Específico",
        readonly=True,
        required=True,
    )
    line_ids = fields.Many2many(
        "contrato.especifico.line",
        relation="lineas_facturar_multiples_wiz_rel",
        string="Líneas a Facturar",
        readonly=True,
    )
    departamento_id = fields.Many2one(
        "res.partner.departamento",
        string="Departamento",
    )
    total_amount = fields.Float(
        string="Total",
        compute="_compute_total_amount",
    )

    @api.depends("line_ids.price_subtotal")
    def _compute_total_amount(self):
        for wiz in self:
            wiz.total_amount = sum(wiz.line_ids.mapped("price_subtotal"))

    def action_confirm(self) -> dict:
        """Crea una única factura con todas las líneas seleccionadas."""
        self.ensure_one()

        lines = self.line_ids.filtered(
            lambda l: not l.invoiced and not l.is_invoice_line
        )
        if not lines:
            raise UserError(
                _("Ninguna de las líneas seleccionadas está pendiente de facturar.")
            )

        contract = self.contrato_id

        if contract.state != "firmado":
            raise UserError(
                _(
                    "Solo puede facturar las líneas de servicio de un contrato que se encuentre Firmado."
                )
            )

        if not contract.forma_pago_id:
            raise UserError(
                _(
                    "Debe configurar la Forma de Pago en los Datos de Facturación del "
                    "contrato antes de facturar."
                )
            )

        for line in lines:
            line._apply_default_invoice_dates()

        partner = contract.partner_id
        invoice_line_ids = [
            (
                0,
                0,
                {
                    "product_id": line.product_id.id,
                    "name": line.name,
                    "quantity": line.quantity,
                    "product_uom_id": line.uom_id.id,
                    "price_unit": line.price_unit,
                    "service_line_id": line.id,
                    "date_deadline_invoice": line.date_deadline_invoice,
                },
            )
            for line in lines
        ]

        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "contrato_especifico_id": contract.id,
                "invoice_payment_term_id": contract.forma_pago_id.id
                if contract.forma_pago_id
                else False,
                "departamento_id": self.departamento_id.id
                if self.departamento_id
                else False,
                "client_address": f"{partner.street or ''} {partner.city or ''}".strip(),
                "client_nit": getattr(partner, "tax_id", None) or partner.vat or "",
                "client_bank_account": getattr(partner, "bank_account_cup", None) or "",
                "realizada_por_id": contract.realizada_por_id.id
                if contract.realizada_por_id
                else False,
                "invoice_line_ids": invoice_line_ids,
            }
        )

        lines.with_context(is_uninvoice=True).write({"invoiced": True})

        return {
            "name": _("Factura"),
            "view_mode": "form",
            "res_model": "account.move",
            "res_id": move.id,
            "type": "ir.actions.act_window",
        }
