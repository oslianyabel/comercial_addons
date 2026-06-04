from odoo import api, fields, models

# ---------------------------------------------------------------------------
# Spanish number-to-words helper
# ---------------------------------------------------------------------------
_UNIDADES = [
    "",
    "UN",
    "DOS",
    "TRES",
    "CUATRO",
    "CINCO",
    "SEIS",
    "SIETE",
    "OCHO",
    "NUEVE",
]
_TEENS = [
    "DIEZ",
    "ONCE",
    "DOCE",
    "TRECE",
    "CATORCE",
    "QUINCE",
    "DIECISÉIS",
    "DIECISIETE",
    "DIECIOCHO",
    "DIECINUEVE",
]
_DECENAS = [
    "",
    "DIEZ",
    "VEINTE",
    "TREINTA",
    "CUARENTA",
    "CINCUENTA",
    "SESENTA",
    "SETENTA",
    "OCHENTA",
    "NOVENTA",
]
_CENTENAS = [
    "",
    "CIEN",
    "DOSCIENTOS",
    "TRESCIENTOS",
    "CUATROCIENTOS",
    "QUINIENTOS",
    "SEISCIENTOS",
    "SETECIENTOS",
    "OCHOCIENTOS",
    "NOVECIENTOS",
]


def _convertir(n):
    if n == 0:
        return ""
    if n < 10:
        return _UNIDADES[n]
    if n < 20:
        return _TEENS[n - 10]
    if n < 30:
        return "VEINTE" if n == 20 else "VEINTI" + _UNIDADES[n - 20]
    if n < 100:
        resto = n % 10
        return _DECENAS[n // 10] + (" Y " + _UNIDADES[resto] if resto else "")
    if n < 1000:
        centena, resto = divmod(n, 100)
        if centena == 1:
            return "CIEN" if resto == 0 else "CIENTO " + _convertir(resto)
        return _CENTENAS[centena] + (" " + _convertir(resto) if resto else "")
    if n < 1_000_000:
        miles, resto = divmod(n, 1000)
        prefix = "MIL" if miles == 1 else _convertir(miles) + " MIL"
        return prefix + (" " + _convertir(resto) if resto else "")
    millones, resto = divmod(n, 1_000_000)
    prefix = "UN MILLÓN" if millones == 1 else _convertir(millones) + " MILLONES"
    return prefix + (" " + _convertir(resto) if resto else "")


def numero_a_letras(numero):
    """Convert a positive number to uppercase Spanish words."""
    if numero == 0:
        return "CERO"
    return _convertir(int(numero)).strip()


class AccountMove(models.Model):
    _inherit = "account.move"

    contrato_especifico_id = fields.Many2one(
        "contrato.especifico", string="Specific Contract"
    )
    suplemento_especifico_id = fields.Many2one(
        "contrato.especifico.suplemento", string="Suplemento"
    )
    service_line_id = fields.Many2one("contrato.especifico.line", string="Service Line")
    ueb_service_line_id = fields.Many2one(
        "contrato.especifico.ueb.line", string="UEB Service Line"
    )
    sup_service_line_id = fields.Many2one(
        "contrato.especifico.suplemento.line", string="Suplemento Service Line"
    )
    sup_ueb_service_line_id = fields.Many2one(
        "contrato.especifico.suplemento.ueb.line", string="Suplemento UEB Service Line"
    )
    payment_form_id = fields.Many2one("signature.payment.form", string="Forma de pago")

    client_address = fields.Char(string="Client Address")
    client_nit = fields.Char(string="Client NIT")
    client_bank_account = fields.Char(string="Bank Account")

    # Empresa (our company entity for this invoice)
    def _default_empresa_id(self):
        return self.env["contratos.empresa"].search(
            [("name", "=", "Soluciones Dteam")], limit=1
        )

    empresa_id = fields.Many2one(
        "contratos.empresa",
        string="Empresa",
        default=_default_empresa_id,
    )
    organismo_id = fields.Many2one(
        "res.partner.organism",
        string="Organismo",
        related="empresa_id.organismo_id",
        store=False,
    )
    unidad_empresa = fields.Char(
        string="Unidad",
        related="empresa_id.unidad",
        store=False,
    )
    direccion_empresa = fields.Char(
        string="Dirección",
        compute="_compute_direccion_empresa",
        store=False,
    )
    nit_empresa = fields.Char(
        string="NIT",
        related="empresa_id.nit",
        store=False,
    )

    # Client-side fields derived from the specific contract
    cliente_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        related="contrato_especifico_id.partner_id",
        store=False,
    )
    direccion_cliente = fields.Char(
        string="Dirección del Cliente",
        compute="_compute_direccion_cliente",
        store=False,
    )
    codigo_cliente = fields.Char(
        string="Código del Cliente",
        related="contrato_especifico_id.marco_id.partner_id.customer_number",
        store=False,
    )
    nit_cliente = fields.Char(
        string="NIT del Cliente",
        related="contrato_especifico_id.marco_id.representative_id.tax_id",
        store=False,
    )
    cuenta_bancaria_cliente = fields.Char(
        string="Cuenta Bancaria del Cliente",
        related="contrato_especifico_id.marco_id.partner_id.bank_account_cup",
        store=False,
    )
    operacion_id = fields.Many2one(
        "contrato.especifico.template",
        string="Operación",
    )
    departamento_id = fields.Many2one(
        "res.partner.departamento",
        string="Departamento",
    )
    num_ins_rcc = fields.Char(string="Número de Ins. RCC")

    # Payment destination (our bank account info from empresa)
    cuenta_pagar = fields.Char(
        string="Cuenta a Pagar",
        related="empresa_id.company_id.bank_account_cup",
        store=False,
    )
    sucursal_pagar = fields.Char(
        string="Sucursal de la Cuenta a Pagar",
        related="empresa_id.company_id.bank_branch_number",
        store=False,
    )
    banco_pagar = fields.Many2one(
        "res.partner",
        string="Banco a Pagar",
        related="empresa_id.company_id.bank_id_ref",
        store=False,
    )

    # Literal amount in Spanish
    total_cup_literal = fields.Char(
        string="Total en CUP (Literal)",
        compute="_compute_total_cup_literal",
        store=False,
    )

    # Transporter additional info
    transportado_ch = fields.Char(string="CH (Transportado por)")
    transportado_lic = fields.Char(string="LIC (Transportado por)")

    # Stamp/seal - reference to a Firmas y Cuños entry
    cunyo_id = fields.Many2one(
        "signature.signature",
        string="Cuño",
    )

    # Roles: Contact + Date
    realizada_por_id = fields.Many2one("res.partner", string="Realizada por")
    realizada_fecha = fields.Date(string="Fecha (Realizada)")

    transportado_por_id = fields.Many2one("res.partner", string="Transportado por")
    transportado_fecha = fields.Date(string="Fecha (Transportado)")

    recibido_por_id = fields.Many2one("res.partner", string="Recibido por")
    recibido_fecha = fields.Date(string="Fecha (Recibido)")

    entregada_por_id = fields.Many2one("res.partner", string="Entregada por")
    entregada_fecha = fields.Date(string="Fecha (Entregada)")

    contabilizada_por_id = fields.Many2one("res.partner", string="Contabilizada por")
    contabilizada_fecha = fields.Date(string="Fecha (Contabilizada)")

    # ------------------------------------------------------------------
    # Computed helpers
    # ------------------------------------------------------------------

    @api.onchange("contrato_especifico_id")
    def _onchange_contrato_especifico_id(self):
        if self.contrato_especifico_id and not self.operacion_id:
            self.operacion_id = self.contrato_especifico_id.template_id

    @api.depends(
        "empresa_id",
        "empresa_id.company_id",
        "empresa_id.company_id.street",
        "empresa_id.company_id.city",
    )
    def _compute_direccion_empresa(self):
        for move in self:
            partner = move.empresa_id.company_id
            parts = [p for p in [partner.street, partner.city] if p]
            move.direccion_empresa = ", ".join(parts) if parts else ""

    @api.depends(
        "contrato_especifico_id",
        "contrato_especifico_id.partner_id",
        "contrato_especifico_id.partner_id.street",
        "contrato_especifico_id.partner_id.city",
    )
    def _compute_direccion_cliente(self):
        for move in self:
            partner = move.contrato_especifico_id.partner_id
            parts = [p for p in [partner.street, partner.city] if p]
            move.direccion_cliente = ", ".join(parts) if parts else ""

    @api.depends("amount_total")
    def _compute_total_cup_literal(self):
        for move in self:
            amount = move.amount_total or 0.0
            enteros = int(amount)
            centavos = round((amount - enteros) * 100)
            letras = numero_a_letras(enteros)
            if centavos:
                move.total_cup_literal = f"{letras} CON {centavos:02d}"
            else:
                move.total_cup_literal = letras

    @api.onchange("contrato_especifico_id")
    def _onchange_contrato_especifico_id_set_operacion(self):
        for move in self:
            if move.contrato_especifico_id and not move.operacion:
                move.operacion = move.contrato_especifico_id.contract_type

    def _report_spaced_text(self, value):
        text = str(value or "").strip()
        return "\u200a".join(text) if text else ""

    def _report_spaced_label(self, value):
        text = str(value or "").strip()
        return "\u2009".join(text) if text else ""

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------

    def write(self, vals):
        result = super().write(vals)
        if "invoice_line_ids" in vals:
            for move in self:
                move._sync_invoice_lines_to_service_lines()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        contrato_model = self.env["contrato.especifico"]
        for vals in vals_list:
            if not vals.get("operacion_id") and vals.get("contrato_especifico_id"):
                contract = contrato_model.browse(vals["contrato_especifico_id"])
                if contract.template_id:
                    vals["operacion_id"] = contract.template_id.id
        records = super().create(vals_list)
        for move in records:
            if move.contrato_especifico_id and move.move_type == "out_invoice":
                move._assign_contrato_invoice_name()
                move._clear_invoice_line_taxes()
        return records

    def _clear_invoice_line_taxes(self) -> None:
        """Remove taxes from all product lines of this contract invoice."""
        self.ensure_one()
        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        )
        if product_lines:
            product_lines.with_context(check_move_validity=False).write(
                {"tax_ids": [(5, 0, 0)]}
            )

    def action_post(self):
        """Strip taxes before confirming contract invoices."""
        for move in self.filtered(
            lambda m: m.contrato_especifico_id and m.move_type == "out_invoice"
        ):
            move._clear_invoice_line_taxes()
        return super().action_post()

    def _assign_contrato_invoice_name(self) -> None:
        """Assign a custom name FACT_<consecutive>_<contract_number> to the invoice."""
        self.ensure_one()
        contract = self.contrato_especifico_id
        if not contract:
            return
        existing_count = self.env["account.move"].search_count(
            [
                ("contrato_especifico_id", "=", contract.id),
                ("id", "!=", self.id),
                ("move_type", "=", "out_invoice"),
            ]
        )
        consecutive = existing_count + 1
        self.with_context(no_resequence=True).write(
            {"name": f"FACT_{consecutive:02d}_{contract.name}"}
        )

    def action_open_contrato_especifico(self) -> dict:
        """Open the linked specific contract form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico",
            "res_id": self.contrato_especifico_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_suplemento_especifico(self) -> dict:
        """Open the linked suplemento form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico.suplemento",
            "res_id": self.suplemento_especifico_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _sync_invoice_lines_to_service_lines(self) -> None:
        """Propagate quantity and price_unit changes from invoice product lines to the linked service line."""
        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        )
        if not product_lines:
            return
        inv_line = product_lines[0]

        all_svc_lines = filter(
            None,
            [
                self.service_line_id,
                self.ueb_service_line_id,
                self.sup_service_line_id,
                self.sup_ueb_service_line_id,
            ],
        )
        for svc_line in all_svc_lines:
            updates: dict = {}
            if svc_line.quantity != inv_line.quantity:
                updates["quantity"] = inv_line.quantity
            if svc_line.price_unit != inv_line.price_unit:
                updates["price_unit"] = inv_line.price_unit
            if updates:
                svc_line.with_context(is_uninvoice=True).write(updates)

    def unlink(self):
        """Reset the 'invoiced' flag on the related service line when the invoice is deleted."""
        service_lines = self.mapped("service_line_id")
        ueb_service_lines = self.mapped("ueb_service_line_id")
        sup_service_lines = self.mapped("sup_service_line_id")
        sup_ueb_service_lines = self.mapped("sup_ueb_service_line_id")
        contracts = service_lines.mapped("contrato_id")

        res = super().unlink()

        if service_lines:
            service_lines.sudo().with_context(is_uninvoice=True).write(
                {"invoiced": False}
            )
            if contracts:
                contracts.sudo()._compute_service_line_state()

        if ueb_service_lines:
            ueb_service_lines.sudo().with_context(is_uninvoice=True).write(
                {"invoiced": False}
            )

        if sup_service_lines:
            sup_service_lines.sudo().with_context(is_uninvoice=True).write(
                {"invoiced": False}
            )

        if sup_ueb_service_lines:
            sup_ueb_service_lines.sudo().with_context(is_uninvoice=True).write(
                {"invoiced": False}
            )

        return res

    contrato_especifico_id = fields.Many2one(
        "contrato.especifico", string="Specific Contract"
    )
    suplemento_especifico_id = fields.Many2one(
        "contrato.especifico.suplemento", string="Suplemento"
    )
    service_line_id = fields.Many2one("contrato.especifico.line", string="Service Line")
    ueb_service_line_id = fields.Many2one(
        "contrato.especifico.ueb.line", string="UEB Service Line"
    )
    sup_service_line_id = fields.Many2one(
        "contrato.especifico.suplemento.line", string="Suplemento Service Line"
    )
    sup_ueb_service_line_id = fields.Many2one(
        "contrato.especifico.suplemento.ueb.line", string="Suplemento UEB Service Line"
    )
    payment_form_id = fields.Many2one("signature.payment.form", string="Forma de pago")

    client_address = fields.Char(string="Client Address")
    client_nit = fields.Char(string="Client NIT")
    client_bank_account = fields.Char(string="Bank Account")

    # Roles: Contact + Date
    realizada_por_id = fields.Many2one("res.partner", string="Realizada por")
    realizada_fecha = fields.Date(string="Fecha (Realizada)")

    transportado_por_id = fields.Many2one("res.partner", string="Transportado por")
    transportado_fecha = fields.Date(string="Fecha (Transportado)")

    recibido_por_id = fields.Many2one("res.partner", string="Recibido por")
    recibido_fecha = fields.Date(string="Fecha (Recibido)")

    entregada_por_id = fields.Many2one("res.partner", string="Entregada por")
    entregada_fecha = fields.Date(string="Fecha (Entregada)")

    contabilizada_por_id = fields.Many2one("res.partner", string="Contabilizada por")
    contabilizada_fecha = fields.Date(string="Fecha (Contabilizada)")

    def write(self, vals):
        result = super().write(vals)
        if "invoice_line_ids" in vals:
            for move in self:
                move._sync_invoice_lines_to_service_lines()
        if "state" in vals:
            new_state = vals["state"]
            for move in self:
                svc_lines = [
                    l
                    for l in [
                        move.service_line_id,
                        move.ueb_service_line_id,
                        move.sup_service_line_id,
                        move.sup_ueb_service_line_id,
                    ]
                    if l
                ]
                for svc_line in svc_lines:
                    svc_line.sudo().with_context(is_uninvoice=True).write(
                        {"invoice_state": new_state}
                    )
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for move in records:
            if move.contrato_especifico_id and move.move_type == "out_invoice":
                move._assign_contrato_invoice_name()
                move._clear_invoice_line_taxes()
            if move.move_type == "out_invoice":
                move._propagate_deadline_to_invoice_lines()
        return records

    def _propagate_deadline_to_invoice_lines(self) -> None:
        """Propagate date_deadline_invoice from the linked service line to the
        first product invoice line. Handles all four service-line types."""
        self.ensure_one()
        svc_line = (
            self.service_line_id
            or self.ueb_service_line_id
            or self.sup_service_line_id
            or self.sup_ueb_service_line_id
        )
        deadline = (
            getattr(svc_line, "date_deadline_invoice", None) if svc_line else None
        )
        if not deadline:
            return
        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        )
        if not product_lines:
            return
        updates: dict = {"date_deadline_invoice": deadline}
        if self.service_line_id and not product_lines[0].service_line_id:
            updates["service_line_id"] = self.service_line_id.id
        product_lines[0].with_context(check_move_validity=False).write(updates)

    def _clear_invoice_line_taxes(self) -> None:
        """Remove taxes from all product lines of this contract invoice."""
        self.ensure_one()
        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        )
        if product_lines:
            product_lines.with_context(check_move_validity=False).write(
                {"tax_ids": [(5, 0, 0)]}
            )

    def action_post(self):
        """Strip taxes before confirming contract invoices."""
        for move in self.filtered(
            lambda m: m.contrato_especifico_id and m.move_type == "out_invoice"
        ):
            move._clear_invoice_line_taxes()
        return super().action_post()

    def button_draft(self):
        """Clear taxes when resetting contract invoices to draft."""
        result = super().button_draft()
        for move in self.filtered(
            lambda m: m.contrato_especifico_id and m.move_type == "out_invoice"
        ):
            move._clear_invoice_line_taxes()
        return result

    def _assign_contrato_invoice_name(self) -> None:
        """Assign a custom name FACT_<consecutive>_<contract_number> to the invoice."""
        self.ensure_one()
        contract = self.contrato_especifico_id
        if not contract:
            return
        existing_count = self.env["account.move"].search_count(
            [
                ("contrato_especifico_id", "=", contract.id),
                ("id", "!=", self.id),
                ("move_type", "=", "out_invoice"),
            ]
        )
        consecutive = existing_count + 1
        self.with_context(no_resequence=True).write(
            {"name": f"FACT_{consecutive:02d}_{contract.name}"}
        )

    def action_open_contrato_especifico(self) -> dict:
        """Open the linked specific contract form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico",
            "res_id": self.contrato_especifico_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_suplemento_especifico(self) -> dict:
        """Open the linked suplemento form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico.suplemento",
            "res_id": self.suplemento_especifico_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _sync_invoice_lines_to_service_lines(self) -> None:
        """Propagate quantity and price_unit changes from invoice product lines to the linked service line."""
        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        )
        if not product_lines:
            return
        inv_line = product_lines[0]

        all_svc_lines = filter(
            None,
            [
                self.service_line_id,
                self.ueb_service_line_id,
                self.sup_service_line_id,
                self.sup_ueb_service_line_id,
            ],
        )
        for svc_line in all_svc_lines:
            updates: dict = {}
            if svc_line.quantity != inv_line.quantity:
                updates["quantity"] = inv_line.quantity
            if svc_line.price_unit != inv_line.price_unit:
                updates["price_unit"] = inv_line.price_unit
            if updates:
                svc_line.with_context(is_uninvoice=True).write(updates)

    def unlink(self):
        """Reset the 'invoiced' flag on the related service line when the invoice is deleted."""
        service_lines = self.mapped("service_line_id")
        ueb_service_lines = self.mapped("ueb_service_line_id")
        sup_service_lines = self.mapped("sup_service_line_id")
        sup_ueb_service_lines = self.mapped("sup_ueb_service_line_id")
        contracts = service_lines.mapped("contrato_id")

        res = super().unlink()

        if service_lines:
            service_lines.sudo().with_context(is_uninvoice=True).write(
                {"invoiced": False}
            )
            if contracts:
                contracts.sudo()._compute_service_line_state()

        if ueb_service_lines:
            ueb_service_lines.sudo().with_context(is_uninvoice=True).write(
                {"invoiced": False}
            )

        if sup_service_lines:
            sup_service_lines.sudo().with_context(is_uninvoice=True).write(
                {"invoiced": False}
            )

        if sup_ueb_service_lines:
            sup_ueb_service_lines.sudo().with_context(is_uninvoice=True).write(
                {"invoiced": False}
            )

        return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    service_line_id = fields.Many2one(
        "contrato.especifico.line",
        string="Línea de Servicio",
        ondelete="set null",
    )
    date_deadline_invoice = fields.Date(
        string="Fecha Límite de Facturación",
        readonly=True,
    )

    @api.depends("product_id", "product_uom_id")
    def _compute_tax_ids(self):
        """This system uses no taxes — always keep tax_ids empty."""
        for line in self:
            if line.display_type not in ("line_section", "line_note", "payment_term"):
                line.tax_ids = self.env["account.tax"]
