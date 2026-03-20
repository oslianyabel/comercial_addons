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
    )
    start_date = fields.Date(string="Fecha de Inicio")
    end_date = fields.Date(string="Fecha Final")
    invoiced = fields.Boolean(string="Facturado", default=False, readonly=True)

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

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
        administrative_fields = {"invoiced"}
        if vals and all(field in administrative_fields for field in vals.keys()):
            return
        for line in self:
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
            if vals.get("section_id"):
                section = self.env["contrato.especifico.ueb.section"].browse(
                    vals["section_id"]
                )
                if section.contrato_id.state == "firmado":
                    raise UserError(
                        _("No puede añadir líneas a un contrato ya firmado.")
                    )
        return super().create(vals_list)

    def write(self, vals: dict) -> bool:
        self._check_signed_contract(vals)
        return super().write(vals)

    def unlink(self) -> bool:
        self._check_signed_contract()
        return super().unlink()

    def action_uninvoice(self) -> None:
        """Reset the invoiced flag and delete associated invoices."""
        for line in self:
            if not line.invoiced:
                continue
            invoices = self.env["account.move"].search(
                [("ueb_service_line_id", "=", line.id)]
            )
            for inv in invoices:
                if inv.state == "posted":
                    inv.button_draft()
                inv.unlink()
            line.with_context(is_uninvoice=True).write({"invoiced": False})

    def action_facturar(self) -> dict:
        """Generate an invoice from this UEB section service line."""
        for line in self:
            if line.invoiced:
                raise UserError(_("Esta línea ya ha sido facturada."))

            contract = line._get_contract()

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

            partner = contract.partner_id
            invoice_vals = {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "contrato_especifico_id": contract.id,
                "ueb_service_line_id": line.id,
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
