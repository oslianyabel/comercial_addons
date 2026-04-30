from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class ContratoEspecificoLine(models.Model):
    _name = "contrato.especifico.line"
    _description = "Specific Contract Service Line"

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
        """Block modifications on signed contracts, unless only updating administrative fields like 'invoiced'."""
        if self._context.get("is_uninvoice"):
            return

        administrative_fields = {"invoiced", "start_date", "end_date"}

        # If vals is provided, check if we are ONLY updating administrative fields
        if vals and all(field in administrative_fields for field in vals.keys()):
            return

        for line in self:
            if line.contrato_id and line.contrato_id.state == "firmado":
                raise UserError(
                    _(
                        "You cannot modify, create or delete service lines for a contract that is already signed."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("contrato_id"):
                contract = self.env["contrato.especifico"].browse(vals["contrato_id"])
                if contract.state == "firmado":
                    raise UserError(
                        _("You cannot add lines to a contract that is already signed.")
                    )
        return super().create(vals_list)

    def write(self, vals):
        self._check_signed_contract(vals)
        return super().write(vals)

    def unlink(self):
        self._check_signed_contract()
        return super().unlink()

    def action_uninvoice(self):
        """Reset the invoiced flag and delete associated invoices."""
        for line in self:
            if not line.invoiced:
                continue
            # Find and delete associated invoices
            invoices = self.env["account.move"].search(
                [("service_line_id", "=", line.id)]
            )
            # Only allow deleting draft or cancelled invoices for safety,
            # but user requested it should delete it.
            # In Odoo, deleting posted invoices usually requires resetting to draft first.
            for inv in invoices:
                if inv.state == "posted":
                    inv.button_draft()
                inv.unlink()

            # Bypass the manual write check by using super().write or context
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
        """Generar la factura desde la línea del contrato sin wizard usando los campos en contrato_especifico."""
        for line in self:
            if line.invoiced:
                raise UserError(_("Esta línea ya ha sido facturada."))

            contract = line.contrato_id

            # Validación: El contrato debe estar firmado para facturarse
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

            partner = contract.partner_id
            line._apply_default_invoice_dates()

            invoice_vals = {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "contrato_especifico_id": contract.id,
                "service_line_id": line.id,
                "invoice_payment_term_id": contract.forma_pago_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": line.product_id.id,
                            "name": line.name,
                            "quantity": line.quantity,
                            "product_uom_id": line.uom_id.id,
                            "price_unit": line.price_unit,
                        },
                    )
                ],
                "client_address": f"{partner.street or ''} {partner.city or ''}".strip(),
                "client_nit": getattr(partner, "tax_id", None) or partner.vat or "",
                "client_bank_account": getattr(partner, "bank_account_cup", None) or "",
                # realizada_por_id is now res.partner (changed from res.users)
                "realizada_por_id": contract.realizada_por_id.id
                if contract.realizada_por_id
                else False,
            }

            move = self.env["account.move"].create(invoice_vals)
            line.with_context(is_uninvoice=True).write({"invoiced": True})

            return {
                "name": _("Factura"),
                "view_mode": "form",
                "res_model": "account.move",
                "res_id": move.id,
                "type": "ir.actions.act_window",
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
