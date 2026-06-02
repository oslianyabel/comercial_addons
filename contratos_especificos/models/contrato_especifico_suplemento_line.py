from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContratoEspecificoSupplementoLine(models.Model):
    _name = "contrato.especifico.suplemento.line"
    _description = "Línea de Servicio de Suplemento de Contrato Específico"
    _order = "sequence, is_invoice_line, id"

    suplemento_id = fields.Many2one(
        "contrato.especifico.suplemento",
        string="Suplemento",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    parent_line_id = fields.Many2one(
        "contrato.especifico.suplemento.line",
        string="Línea Padre",
        ondelete="set null",
    )
    is_invoice_line = fields.Boolean(
        string="Es Línea de Factura",
        default=False,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto/Servicio",
        required=True,
    )
    name = fields.Char(string="Descripción", required=True)
    quantity = fields.Float(string="Cantidad", default=1.0, required=True)
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unidad de Medida",
        required=True,
    )
    price_unit = fields.Float(string="Precio Unitario (CUP)", required=True)
    price_subtotal = fields.Float(
        string="Subtotal",
        compute="_compute_price_subtotal",
        store=True,
    )
    date_deadline_invoice = fields.Date(string="Fecha Límite de Facturación")
    start_date = fields.Date(string="Fecha de Inicio")
    end_date = fields.Date(string="Fecha Final")
    original_invoiced = fields.Boolean(
        string="Fue Facturada",
        default=False,
        help="Indica que la línea original ya estaba facturada al crear este suplemento.",
    )
    invoiced = fields.Boolean(
        string="Facturada",
        default=False,
        readonly=True,
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Factura",
        compute="_compute_invoice_data",
    )
    invoice_state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("posted", "Publicado"),
            ("cancel", "Cancelado"),
        ],
        string="Estado de Factura",
        compute="_compute_invoice_data",
    )

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self) -> None:
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    def _compute_invoice_data(self) -> None:
        for line in self:
            invoice = self.env["account.move"].search(
                [("sup_service_line_id", "=", line.id)], limit=1
            )
            line.invoice_id = invoice
            line.invoice_state = invoice.state if invoice else False

    def write(self, vals: dict) -> bool:
        if not self._context.get("is_uninvoice"):
            if "quantity" in vals or "price_unit" in vals:
                for line in self:
                    if line.invoiced:
                        raise UserError(
                            _(
                                "No puede modificar la cantidad ni el precio de una línea ya facturada. "
                                "Modifíquelos desde la vista de la factura."
                            )
                        )
        return super().write(vals)

    def _apply_default_invoice_dates(self) -> None:
        """Fill start_date / end_date if still empty (best-effort)."""
        from datetime import timedelta

        for line in self:
            if not line.start_date:
                line.with_context(is_uninvoice=True).write(
                    {"start_date": fields.Date.today()}
                )
            if not line.end_date and line.start_date:
                line.with_context(is_uninvoice=True).write(
                    {"end_date": line.start_date + timedelta(days=30)}
                )

    def action_facturar(self) -> dict:
        """Open billing wizard for this suplemento service line."""
        self.ensure_one()
        sup = self.suplemento_id
        if sup.state != "firmado":
            raise UserError(
                _(
                    "Solo se pueden facturar líneas de suplementos firmados. "
                    "El suplemento '%s' está en estado '%s'.",
                    sup.name,
                    sup.state,
                )
            )
        if not sup.forma_pago_id:
            raise UserError(
                _(
                    "El suplemento '%s' no tiene forma de pago configurada. "
                    "Configure una antes de facturar.",
                    sup.name,
                )
            )
        wizard = self.env["contrato.especifico.facturar.wizard"].create(
            {
                "sup_line_id": self.id,
                "max_quantity": self.quantity,
                "max_price": self.price_unit,
                "quantity": self.quantity,
                "price_unit": self.price_unit,
            }
        )
        return {
            "name": _("Facturar Línea de Servicio"),
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico.facturar.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_uninvoice(self) -> None:
        """Cancel/delete the associated invoice and reset the invoiced flag."""
        for line in self:
            if not line.invoiced:
                continue
            invoices = self.env["account.move"].search(
                [("sup_service_line_id", "=", line.id)]
            )
            if line.is_invoice_line:
                invoices.button_cancel()
            else:
                invoices.button_cancel()
                invoices.unlink()
                line.with_context(is_uninvoice=True).write({"invoiced": False})

    def action_view_invoice(self) -> dict:
        """Open the linked invoice form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "target": "current",
        }
