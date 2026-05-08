from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContratoEspecificoUebSection(models.Model):
    _name = "contrato.especifico.ueb.section"
    _description = "UEB Section in Specific Contract"
    _order = "sequence, id"

    contrato_id = fields.Many2one(
        "contrato.especifico",
        string="Contrato Específico",
        required=True,
        ondelete="cascade",
    )
    ueb_id = fields.Many2one(
        "res.partner.ueb",
        string="UEB",
        required=True,
    )
    sequence = fields.Integer(default=10)
    contract_state = fields.Selection(
        related="contrato_id.state",
        string="Estado del Contrato",
        store=False,
    )
    line_ids = fields.One2many(
        "contrato.especifico.ueb.line",
        "section_id",
        string="Líneas de Servicio",
    )
    line_count = fields.Integer(
        string="Nº de Líneas",
        compute="_compute_line_count",
    )
    total_amount = fields.Float(
        string="Total",
        compute="_compute_total_amount",
    )

    _sql_constraints = [
        (
            "unique_ueb_per_contract",
            "UNIQUE(contrato_id, ueb_id)",
            "Esta UEB ya tiene una tabla de líneas de servicio en este contrato.",
        )
    ]

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends("line_ids.price_subtotal")
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped("price_subtotal"))


class ContratoEspecificoUebLine(models.Model):
    _name = "contrato.especifico.ueb.line"
    _description = "Service Line for UEB Section"
    _order = "sequence, is_invoice_line, id"

    sequence = fields.Integer(string="Sequence", default=10)
    parent_line_id = fields.Many2one(
        "contrato.especifico.ueb.line",
        string="Parent Line",
        ondelete="set null",
    )
    is_invoice_line = fields.Boolean(
        string="Is Invoice Line",
        default=False,
    )
    section_id = fields.Many2one(
        "contrato.especifico.ueb.section",
        string="Sección UEB",
        required=True,
        ondelete="cascade",
    )
    contrato_id = fields.Many2one(
        "contrato.especifico",
        related="section_id.contrato_id",
        store=True,
        string="Contrato",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto/Servicio",
        required=True,
    )
    name = fields.Char(string="Descripción", required=True)
    quantity = fields.Float(string="Cantidad", default=1.0, required=True)
    uom_id = fields.Many2one("uom.uom", string="UdM", required=True)
    price_unit = fields.Float(string="Precio Unitario", required=True)
    price_subtotal = fields.Float(
        string="Subtotal",
        compute="_compute_price_subtotal",
        store=True,
    )
    date_deadline_invoice = fields.Date(
        string="Fecha Límite de Facturación",
        required=True,
        default=lambda self: fields.Date.today() + timedelta(days=30),
    )
    start_date = fields.Date(string="Fecha de Inicio")
    end_date = fields.Date(string="Fecha Final")
    invoiced = fields.Boolean(string="Facturado", default=False, readonly=True)
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
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    def _compute_invoice_data(self):
        for line in self:
            invoice = self.env["account.move"].search(
                [("ueb_service_line_id", "=", line.id)], limit=1
            )
            line.invoice_id = invoice
            line.invoice_state = invoice.state if invoice else False

    @staticmethod
    def _get_end_date_from_start(start_date):
        return start_date + timedelta(days=30) if start_date else False

    @api.onchange("start_date")
    def _onchange_start_date(self):
        for line in self:
            line.end_date = line._get_end_date_from_start(line.start_date)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id.id
            self.price_unit = self.product_id.lst_price

    def _get_contract(self) -> "models.Model":
        return self.section_id.contrato_id

    def _check_signed_contract(self, vals: dict | None = None) -> None:
        if self._context.get("is_uninvoice"):
            return
        administrative_fields = {
            "invoiced",
            "start_date",
            "end_date",
            "is_invoice_line",
            "sequence",
            "parent_line_id",
        }
        if vals and all(field in administrative_fields for field in vals.keys()):
            return
        for line in self:
            if line.is_invoice_line:
                continue
            contract = line._get_contract()
            if contract and contract.state == "firmado":
                raise UserError(
                    _(
                        "No puede modificar, crear ni eliminar líneas de servicio "
                        "de un contrato ya firmado."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> "ContratoEspecificoUebLine":
        for vals in vals_list:
            is_invoice_line = vals.get("is_invoice_line", False)
            if is_invoice_line:
                continue
            if vals.get("section_id"):
                section = self.env["contrato.especifico.ueb.section"].browse(
                    vals["section_id"]
                )
                if section.contrato_id.state == "firmado":
                    raise UserError(
                        _("No puede añadir líneas a un contrato ya firmado.")
                    )
        records = super().create(vals_list)
        for record in records:
            if not record.parent_line_id and not record.is_invoice_line:
                sibling_sequences = (
                    self.env["contrato.especifico.ueb.line"]
                    .search(
                        [
                            ("section_id", "=", record.section_id.id),
                            ("id", "!=", record.id),
                            ("is_invoice_line", "=", False),
                        ]
                    )
                    .mapped("sequence")
                )
                max_seq = max(sibling_sequences, default=0)
                if record.sequence == 10 and max_seq >= 10:
                    record.with_context(is_uninvoice=True).write(
                        {"sequence": max_seq + 10}
                    )
            elif record.parent_line_id:
                record.with_context(is_uninvoice=True).write(
                    {"sequence": record.parent_line_id.sequence}
                )
        return records

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
        self._check_signed_contract(vals)
        return super().write(vals)

    def unlink(self) -> bool:
        self._check_signed_contract()
        return super().unlink()

    def action_uninvoice(self) -> None:
        """Cancel the associated invoice. For invoice lines (partial history), only cancel the invoice.
        For regular lines, delete the invoice and reset the invoiced flag."""
        for line in self:
            if not line.invoiced:
                continue
            invoices = self.env["account.move"].search(
                [("ueb_service_line_id", "=", line.id)]
            )
            if line.is_invoice_line:
                for inv in invoices:
                    if inv.state == "posted":
                        inv.button_draft()
                    if inv.state != "cancel":
                        inv.button_cancel()
                line.with_context(is_uninvoice=True).write({"invoiced": False})
            else:
                for inv in invoices:
                    if inv.state == "posted":
                        inv.button_draft()
                    inv.unlink()
                line.with_context(is_uninvoice=True).write({"invoiced": False})

    def action_view_invoice(self) -> dict:
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No existe una factura asociada a esta línea."))
        return {
            "name": _("Factura"),
            "view_mode": "form",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "type": "ir.actions.act_window",
        }

    def _apply_default_invoice_dates(self) -> None:
        today = fields.Date.today()
        values = {}
        if not self.start_date:
            values["start_date"] = today
        if not self.end_date:
            base_start_date = values.get("start_date") or self.start_date or today
            values["end_date"] = self._get_end_date_from_start(base_start_date)
        if values:
            self.with_context(is_uninvoice=True).write(values)

    def action_facturar(self) -> dict:
        """Abrir el wizard de facturación para especificar cantidad y precio a facturar."""
        self.ensure_one()

        if self.invoiced:
            raise UserError(_("Esta línea ya ha sido facturada."))

        contract = self._get_contract()

        if contract.state != "firmado":
            raise UserError(
                _(
                    "Solo puede facturar las líneas de servicio de un contrato "
                    "que se encuentre Firmado."
                )
            )
        if not contract.forma_pago_id:
            raise UserError(
                _(
                    "Debe configurar la Forma de Pago en los Datos de Facturación "
                    "del contrato antes de facturar."
                )
            )

        wizard = self.env["contrato.especifico.facturar.wizard"].create(
            {
                "ueb_line_id": self.id,
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


class ContratoEspecificoAddUebWizard(models.TransientModel):
    _name = "contrato.especifico.add.ueb.wizard"
    _description = "Wizard para agregar tabla de líneas de servicio por UEB"

    contrato_id = fields.Many2one(
        "contrato.especifico",
        required=True,
        readonly=True,
    )
    available_ueb_ids = fields.Many2many(
        "res.partner.ueb",
        compute="_compute_available_ueb_ids",
    )
    ueb_id = fields.Many2one(
        "res.partner.ueb",
        string="UEB",
        required=True,
        domain="[('id', 'in', available_ueb_ids)]",
    )

    @api.depends("contrato_id", "contrato_id.partner_id", "contrato_id.ueb_section_ids")
    def _compute_available_ueb_ids(self) -> None:
        for rec in self:
            if rec.contrato_id:
                partner_uebs = rec.contrato_id.partner_id.ueb_ids
                already_added = rec.contrato_id.ueb_section_ids.mapped("ueb_id")
                rec.available_ueb_ids = partner_uebs - already_added
            else:
                rec.available_ueb_ids = self.env["res.partner.ueb"]

    def action_confirm(self) -> dict:
        self.env["contrato.especifico.ueb.section"].create(
            {
                "contrato_id": self.contrato_id.id,
                "ueb_id": self.ueb_id.id,
            }
        )
        return {"type": "ir.actions.act_window_close"}
