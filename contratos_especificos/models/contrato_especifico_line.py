from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class ContratoEspecificoLine(models.Model):
    _name = "contrato.especifico.line"
    _description = "Specific Contract Service Line"
    _order = "sequence, is_invoice_line, id"

    sequence = fields.Integer(string="Sequence", default=10)
    parent_line_id = fields.Many2one(
        "contrato.especifico.line",
        string="Parent Line",
        ondelete="set null",
    )
    is_invoice_line = fields.Boolean(
        string="Is Invoice Line",
        default=False,
    )
    contrato_id = fields.Many2one(
        "contrato.especifico",
        string="Specific Contract",
        ondelete="cascade",
        required=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Service/Product",
        required=True,
    )
    name = fields.Char(string="Description", required=True)
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        required=True,
    )
    price_unit = fields.Float(string="Unit Price (CUP)", required=True)
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
    invoiced = fields.Boolean(
        string="Invoiced",
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
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    def _compute_invoice_data(self):
        for line in self:
            invoice = self.env["account.move"].search(
                [("service_line_id", "=", line.id)], limit=1
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

    def _check_signed_contract(self, vals=None):
        """Block modifications on signed contracts, unless only updating administrative fields."""
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

        # If vals is provided, check if we are ONLY updating administrative fields
        if vals and all(field in administrative_fields for field in vals.keys()):
            return

        for line in self:
            # Invoice lines (partial billing history) are always allowed on signed contracts
            if line.is_invoice_line:
                continue
            if line.contrato_id and line.contrato_id.state == "firmado":
                raise UserError(
                    _(
                        "You cannot modify, create or delete service lines for a contract that is already signed."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            is_invoice_line = vals.get("is_invoice_line", False)
            # Invoice lines (partial billing history) are always allowed on signed contracts
            if is_invoice_line:
                continue
            if vals.get("contrato_id"):
                contract = self.env["contrato.especifico"].browse(vals["contrato_id"])
                if contract.state == "firmado":
                    raise UserError(
                        _("You cannot add lines to a contract that is already signed.")
                    )
        records = super().create(vals_list)
        # Assign sequence after creation for lines without explicit sequence
        for record in records:
            if not record.parent_line_id and not record.is_invoice_line:
                sibling_sequences = (
                    self.env["contrato.especifico.line"]
                    .search(
                        [
                            ("contrato_id", "=", record.contrato_id.id),
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

    def write(self, vals):
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

    def unlink(self):
        self._check_signed_contract()
        return super().unlink()

    def action_uninvoice(self):
        """Cancel the associated invoice. For invoice lines (partial history), only cancel the invoice.
        For regular lines, delete the invoice and reset the invoiced flag."""
        for line in self:
            if not line.invoiced:
                continue

            invoices = self.env["account.move"].search(
                [("service_line_id", "=", line.id)]
            )

            if line.is_invoice_line:
                # Invoice lines: only cancel the invoice, preserve the history line
                for inv in invoices:
                    if inv.state == "posted":
                        inv.button_draft()
                    if inv.state != "cancel":
                        inv.button_cancel()
                line.with_context(is_uninvoice=True).write({"invoiced": False})
            else:
                # Regular lines: delete the invoice and reset the flag
                for inv in invoices:
                    if inv.state == "posted":
                        inv.button_draft()
                    inv.unlink()
                line.with_context(is_uninvoice=True).write({"invoiced": False})

    def action_view_invoice(self):
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

    def _apply_default_invoice_dates(self):
        today = fields.Date.today()
        values = {}
        if not self.start_date:
            values["start_date"] = today
        if not self.end_date:
            base_start_date = values.get("start_date") or self.start_date or today
            values["end_date"] = self._get_end_date_from_start(base_start_date)
        if values:
            self.with_context(is_uninvoice=True).write(values)

    def action_facturar(self):
        """Abrir el wizard de facturación para especificar cantidad y precio a facturar."""
        self.ensure_one()

        if self.invoiced:
            raise UserError(_("Esta línea ya ha sido facturada."))

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
                    "Debe configurar la Forma de Pago en los Datos de Facturación del contrato antes de facturar."
                )
            )

        wizard = self.env["contrato.especifico.facturar.wizard"].create(
            {
                "line_id": self.id,
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

    @api.model
    def _name_search(
        self,
        name="",
        args=None,
        operator="ilike",
        limit=100,
        name_get_uid=None,
        order=None,
    ):
        domain = args or []
        if name:
            search_domain = expression.OR(
                [
                    [("name", operator, name)],
                    [("contrato_id.partner_id.name", operator, name)],
                    [("contrato_id.name", operator, name)],
                ]
            )
            domain = expression.AND([domain, search_domain])
        return self._search(
            domain,
            limit=limit,
            access_rights_uid=name_get_uid,
            order=order,
        )
