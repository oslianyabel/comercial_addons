from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContratoEspecificoSupplementoUebSection(models.Model):
    _name = "contrato.especifico.suplemento.ueb.section"
    _description = "Sección UEB de Suplemento de Contrato Específico"
    _order = "sequence, id"

    suplemento_id = fields.Many2one(
        "contrato.especifico.suplemento",
        string="Suplemento",
        required=True,
        ondelete="cascade",
    )
    ueb_id = fields.Many2one(
        "res.partner.ueb",
        string="UEB",
        required=True,
    )
    sequence = fields.Integer(default=10)
    line_ids = fields.One2many(
        "contrato.especifico.suplemento.ueb.line",
        "section_id",
        string="Líneas de Servicio",
    )
    total_amount = fields.Float(
        string="Total",
        compute="_compute_total_amount",
    )

    @api.depends("line_ids.price_subtotal")
    def _compute_total_amount(self) -> None:
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped("price_subtotal"))


class ContratoEspecificoSupplementoUebLine(models.Model):
    _name = "contrato.especifico.suplemento.ueb.line"
    _description = "Línea de Servicio UEB de Suplemento de Contrato Específico"
    _order = "sequence, is_invoice_line, id"

    section_id = fields.Many2one(
        "contrato.especifico.suplemento.ueb.section",
        string="Sección UEB",
        required=True,
        ondelete="cascade",
    )
    suplemento_id = fields.Many2one(
        "contrato.especifico.suplemento",
        related="section_id.suplemento_id",
        store=True,
        string="Suplemento",
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    parent_line_id = fields.Many2one(
        "contrato.especifico.suplemento.ueb.line",
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
                [("sup_ueb_service_line_id", "=", line.id)], limit=1
            )
            line.invoice_id = invoice
            line.invoice_state = invoice.state if invoice else False

    def _get_suplemento(self):
        """Return the parent suplemento record."""
        return self.section_id.suplemento_id

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
        """Open billing wizard for this UEB suplemento service line."""
        self.ensure_one()
        sup = self._get_suplemento()
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
                "sup_ueb_line_id": self.id,
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
                [("sup_ueb_service_line_id", "=", line.id)]
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
