from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContratoEspecificoFacturarWizard(models.TransientModel):
    _name = "contrato.especifico.facturar.wizard"
    _description = "Wizard de Facturación de Línea de Servicio"

    line_id = fields.Many2one(
        "contrato.especifico.line",
        string="Línea de Servicio",
        readonly=True,
    )
    ueb_line_id = fields.Many2one(
        "contrato.especifico.ueb.line",
        string="Línea UEB",
        readonly=True,
    )
    sup_line_id = fields.Many2one(
        "contrato.especifico.suplemento.line",
        string="Línea de Suplemento",
        readonly=True,
    )
    sup_ueb_line_id = fields.Many2one(
        "contrato.especifico.suplemento.ueb.line",
        string="Línea UEB de Suplemento",
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto/Servicio",
        compute="_compute_display_fields",
        readonly=True,
    )
    line_name = fields.Char(
        string="Descripción",
        compute="_compute_display_fields",
        readonly=True,
    )
    max_quantity = fields.Float(string="Cantidad Máxima", readonly=True)
    max_price = fields.Float(string="Precio Máximo", readonly=True)
    quantity = fields.Float(string="Cantidad a Facturar", required=True)
    price_unit = fields.Float(string="Precio Unitario a Facturar", required=True)
    departamento_id = fields.Many2one(
        "res.partner.departamento",
        string="Departamento",
        required=True,
    )

    @api.depends("line_id", "ueb_line_id", "sup_line_id", "sup_ueb_line_id")
    def _compute_display_fields(self) -> None:
        for rec in self:
            src = (
                rec.line_id or rec.ueb_line_id or rec.sup_line_id or rec.sup_ueb_line_id
            )
            rec.product_id = src.product_id if src else False
            rec.line_name = src.name if src else ""

    @api.onchange("quantity")
    def _onchange_quantity(self):
        if self.quantity and self.max_quantity and self.quantity > self.max_quantity:
            self.quantity = self.max_quantity
            return {
                "warning": {
                    "title": _("Cantidad excedida"),
                    "message": _(
                        "La cantidad no puede ser mayor a la cantidad máxima (%(max)s).",
                        max=self.max_quantity,
                    ),
                }
            }

    @api.onchange("price_unit")
    def _onchange_price_unit(self):
        if self.price_unit and self.max_price and self.price_unit > self.max_price:
            self.price_unit = self.max_price
            return {
                "warning": {
                    "title": _("Precio excedido"),
                    "message": _(
                        "El precio no puede ser mayor al precio máximo (%(max)s).",
                        max=self.max_price,
                    ),
                }
            }

    def action_set_max_quantity(self) -> dict:
        """Asignar la cantidad máxima y reabrir el wizard."""
        self.ensure_one()
        self.quantity = self.max_quantity
        return {
            "name": _("Facturar Línea de Servicio"),
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico.facturar.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_set_max_price(self) -> dict:
        """Asignar el precio máximo y reabrir el wizard."""
        self.ensure_one()
        self.price_unit = self.max_price
        return {
            "name": _("Facturar Línea de Servicio"),
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico.facturar.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm(self) -> dict:
        """Crear la factura con la cantidad y precio indicados.

        Si los valores son iguales al máximo → facturación total (comportamiento clásico).
        Si son menores → facturación parcial: actualiza la línea original con el residual
        y crea una línea hija que representa la factura emitida.
        """
        self.ensure_one()

        if self.quantity <= 0:
            raise UserError(_("La cantidad a facturar debe ser mayor a cero."))
        if self.price_unit < 0:
            raise UserError(_("El precio unitario no puede ser negativo."))
        if self.quantity > self.max_quantity:
            raise UserError(
                _(
                    "La cantidad a facturar (%(qty)s) no puede superar la cantidad máxima (%(max)s).",
                    qty=self.quantity,
                    max=self.max_quantity,
                )
            )
        if self.price_unit > self.max_price:
            raise UserError(
                _(
                    "El precio a facturar (%(price)s) no puede superar el precio máximo (%(max)s).",
                    price=self.price_unit,
                    max=self.max_price,
                )
            )

        is_sup_ueb = bool(self.sup_ueb_line_id)
        is_sup = bool(self.sup_line_id)
        is_ueb = bool(self.ueb_line_id)

        if is_sup_ueb:
            line = self.sup_ueb_line_id
        elif is_sup:
            line = self.sup_line_id
        elif is_ueb:
            line = self.ueb_line_id
        else:
            line = self.line_id

        if not line:
            raise UserError(_("No hay ninguna línea de servicio seleccionada."))

        # Obtener contrato/suplemento y partner según el tipo de línea
        if is_sup or is_sup_ueb:
            sup = line._get_suplemento() if is_sup_ueb else line.suplemento_id
            contract = sup.contrato_id
            partner = sup.partner_id
            forma_pago = sup.forma_pago_id
            realizada_por = sup.realizada_por_id
        else:
            sup = None
            contract = line._get_contract() if is_ueb else line.contrato_id
            partner = contract.partner_id
            forma_pago = contract.forma_pago_id
            realizada_por = contract.realizada_por_id

        line._apply_default_invoice_dates()

        is_partial = (
            self.quantity < self.max_quantity or self.price_unit < self.max_price
        )

        if is_partial:
            child_vals: dict = {
                "product_id": line.product_id.id,
                "name": line.name,
                "quantity": self.quantity,
                "uom_id": line.uom_id.id,
                "price_unit": self.price_unit,
                "date_deadline_invoice": getattr(line, "date_deadline_invoice", False),
                "start_date": line.start_date,
                "end_date": line.end_date,
                "parent_line_id": line.id,
                "is_invoice_line": True,
                "invoiced": True,
                "sequence": line.sequence,
            }
            if is_sup_ueb:
                child_vals["section_id"] = line.section_id.id
                child_line = self.env["contrato.especifico.suplemento.ueb.line"].create(
                    child_vals
                )
            elif is_sup:
                child_vals["suplemento_id"] = sup.id
                child_line = self.env["contrato.especifico.suplemento.line"].create(
                    child_vals
                )
            elif is_ueb:
                child_vals["section_id"] = line.section_id.id
                child_line = self.env["contrato.especifico.ueb.line"].create(child_vals)
            else:
                child_vals["contrato_id"] = contract.id
                child_line = self.env["contrato.especifico.line"].create(child_vals)

            billing_line = child_line

            residual_quantity = self.max_quantity - self.quantity
            residual_price = self.max_price - self.price_unit
            # Si la facturación parcial solo redujo el precio pero no la cantidad
            # (ej: UdM=Unidades, cantidad=1), la línea residual conserva la cantidad original
            # para que pueda volver a facturarse sin fallar la validación de cantidad > 0.
            if residual_quantity <= 0 and self.price_unit < self.max_price:
                residual_quantity = self.max_quantity
            line.with_context(is_uninvoice=True).write(
                {
                    "quantity": residual_quantity,
                    "price_unit": residual_price,
                }
            )
        else:
            billing_line = line
            line.with_context(is_uninvoice=True).write({"invoiced": True})

        # Campo del modelo account.move para la línea
        if is_sup_ueb:
            invoice_line_field = "sup_ueb_service_line_id"
        elif is_sup:
            invoice_line_field = "sup_service_line_id"
        elif is_ueb:
            invoice_line_field = "ueb_service_line_id"
        else:
            invoice_line_field = "service_line_id"

        base_invoice_vals: dict = {
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_date": fields.Date.today(),
            "contrato_especifico_id": contract.id if contract else False,
            "suplemento_especifico_id": sup.id if sup else False,
            invoice_line_field: billing_line.id,
            "invoice_payment_term_id": forma_pago.id if forma_pago else False,
            "departamento_id": self.departamento_id.id
            if self.departamento_id
            else False,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": billing_line.product_id.id,
                        "name": billing_line.name,
                        "quantity": self.quantity,
                        "product_uom_id": billing_line.uom_id.id,
                        "price_unit": self.price_unit,
                        "tax_ids": [(5, 0, 0)],
                    },
                )
            ],
            "client_address": f"{partner.street or ''} {partner.city or ''}".strip(),
            "client_nit": getattr(partner, "tax_id", None) or partner.vat or "",
            "client_bank_account": getattr(partner, "bank_account_cup", None) or "",
            "realizada_por_id": realizada_por.id if realizada_por else False,
        }

        move = self.env["account.move"].create(base_invoice_vals)

        return {
            "name": _("Factura"),
            "view_mode": "form",
            "res_model": "account.move",
            "res_id": move.id,
            "type": "ir.actions.act_window",
        }
