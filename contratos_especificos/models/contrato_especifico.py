import re
from datetime import date as pydate
from html import unescape

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class ContratoEspecifico(models.Model):
    _name = "contrato.especifico"
    _description = "Specific Contract"
    _order = "name desc"

    name = fields.Char(string="Contract Number", required=True, default="/")
    marco_id = fields.Many2one(
        "contrato.marco",
        string="Master Contract",
        required=True,
        domain=[("state", "=", "firmado")],
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="marco_id.company_id",
        store=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        related="marco_id.partner_id",
        store=True,
    )
    contract_type = fields.Selection(
        related="marco_id.contract_type",
        string="Contract Type",
        store=True,
    )
    template_id = fields.Many2one(
        "contrato.especifico.template",
        string="Template",
        required=True,
    )
    our_representative_id = fields.Many2one(
        "res.partner",
        string="Our Representative",
        related="marco_id.our_representative_id",
        readonly=True,
    )
    our_rep_decision_number = fields.Char(
        string="Our Rep. Decision Number",
        related="our_representative_id.current_resolution_number",
        readonly=True,
    )
    our_rep_decision_date = fields.Date(
        string="Our Rep. Decision Date",
        related="our_representative_id.current_creation_date",
        readonly=True,
    )
    our_project_leader_id = fields.Many2one(
        "res.partner",
        string="Líder del Proyecto Nuestro",
        domain="[('is_company', '=', False), ('company_id', '=', company_id)]",
    )
    project_leader_id = fields.Many2one(
        "res.partner",
        string="Líder del Proyecto del Cliente",
    )

    # Fields updated automatically by the ORM (computed stored or system fields)
    _SYSTEM_WRITE_ALLOWED = frozenset(
        ["state", "service_line_state", "invoice_count", "end_date"]
    )

    def write(self, vals):
        """Prevent editing signed contracts.

        Allows state transitions and ORM-managed computed stored fields.
        Delivered ('entregado') contracts remain editable.
        """
        if not self.env.su and not vals.keys() <= self._SYSTEM_WRITE_ALLOWED:
            for record in self:
                if record.state == "firmado":
                    raise UserError(
                        _("No puede modificar un contrato que ya está firmado.")
                    )
        return super().write(vals)

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
                    [("partner_id.name", operator, name)],
                ]
            )
            domain = expression.AND([domain, search_domain])
        return self._search(
            domain,
            limit=limit,
            access_rights_uid=name_get_uid,
            order=order,
        )

    template_type_requires_rep = fields.Boolean(
        compute="_compute_template_type_flags",
        store=False,
    )
    template_type_requires_leader = fields.Boolean(
        compute="_compute_template_type_flags",
        store=False,
    )
    template_type_requires_application_name = fields.Boolean(
        compute="_compute_template_type_flags",
        store=False,
    )
    application_name = fields.Char(string="Application Name")

    date = fields.Date(
        string="Subscription Date",
        default=fields.Date.context_today,
    )
    validity_years = fields.Integer(
        string="Vigencia (años)",
        default=lambda self: self._default_validity_years(),
    )
    start_date = fields.Date(string="Effective Date")
    end_date = fields.Date(
        string="End Date",
        compute="_compute_end_date",
        store=True,
    )

    state = fields.Selection(
        [
            ("borrador", "Draft"),
            ("entregado", "Entregado"),
            ("firmado", "Signed"),
            ("cancelado", "Cancelled"),
        ],
        string="Status",
        default="borrador",
        required=True,
        copy=False,
    )

    content = fields.Html(string="Contract Content")
    line_ids = fields.One2many(
        "contrato.especifico.line",
        "contrato_id",
        string="Service Lines",
    )

    # Billing Data Fields (Phase 4)
    realizada_por_id = fields.Many2one(
        "res.partner",
        string="Realizada por",
        default=lambda self: self.env.user.partner_id,
    )
    transportado_por_id = fields.Many2one(
        "res.partner",
        string="Transportado por",
    )
    recibido_por_id = fields.Many2one(
        "res.partner",
        string="Recibido por",
    )
    entregada_por_id = fields.Many2one(
        "res.partner",
        string="Entregada por",
    )
    contabilizada_por_id = fields.Many2one(
        "res.partner",
        string="Contabilizada por",
    )
    forma_pago_id = fields.Many2one("account.payment.term", string="Forma de Pago")

    # UEB service line sections (one table per UEB)
    ueb_section_ids = fields.One2many(
        "contrato.especifico.ueb.section",
        "contrato_id",
        string="Líneas de Servicio por UEB",
    )

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "The Contract Number must be unique. A specific contract "
            "with this number already exists.",
        )
    ]

    @api.model
    def _default_validity_years(self) -> int:
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("contratos.specific_contract_validity_years", default="1")
        )
        try:
            return int(param)
        except (TypeError, ValueError):
            return 1

    @api.depends("start_date", "validity_years")
    def _compute_end_date(self):
        for record in self:
            if record.start_date and record.validity_years:
                record.end_date = self._add_years(
                    record.start_date, record.validity_years
                )
            else:
                record.end_date = False

    @staticmethod
    def _add_years(value, years):
        if not value or not years:
            return value
        try:
            return value.replace(year=value.year + years)
        except ValueError:
            if value.month == 2 and value.day == 29:
                return pydate(value.year + years, 2, 28)
            raise

    @api.depends("template_id", "template_id.type")
    def _compute_template_type_flags(self):
        for record in self:
            t = record.template_id.type if record.template_id else False
            record.template_type_requires_rep = t in (
                "cgm_disponibilidad",
                "productos_soporte",
            )
            record.template_type_requires_leader = t == "versat_iniciales"
            record.template_type_requires_application_name = t in (
                "productos_soporte",
                "soporte_desarrollo",
            )

    def action_generate_content(self):
        for record in self:
            if not record.template_id or not record.template_id.content:
                raise UserError(
                    _("Please select a template with content before generating.")
                )

            from html import unescape

            content = unescape(str(record.template_id.content or ""))
            p = record.partner_id
            marco = record.marco_id
            our_r = record.our_representative_id

            missing = []
            if not record.our_representative_id:
                missing.append(_("Our Representative"))
            if not marco:
                missing.append(_("Master Contract"))
            if (
                record.template_type_requires_application_name
                and not record.application_name
            ):
                missing.append(_("Application Name"))

            if missing:
                raise UserError(
                    _(
                        "The contract cannot be generated because the "
                        "following data is missing:\n\n- %s"
                    )
                    % "\n- ".join(missing)
                )

            def highlight(val):
                return (
                    '<strong style="font-weight: bold; text-decoration: '
                    'underline; color: #000080;">' + str(val or "") + "</strong>"
                )

            def fmt_date(d):
                return (
                    highlight(d.strftime("%d/%m/%Y"))
                    if d
                    else highlight("__________________")
                )

            vals = {
                "specific_number": highlight(record.name),
                "marco_number": highlight(marco.name),
                "marco_date": fmt_date(marco.start_date),
                "our_representative": highlight(our_r.name if our_r else ""),
                "our_rep_function": highlight(our_r.function if our_r else ""),
                "our_rep_decision_number": highlight(record.our_rep_decision_number),
                "partner_name": highlight(p.name),
                "partner_short_name": highlight(p.short_name),
                "project_leader": highlight(
                    record.project_leader_id.name if record.project_leader_id else ""
                ),
                "application_name": highlight(record.application_name or ""),
                "start_date": fmt_date(record.start_date),
                "validity_years": highlight(record.validity_years or ""),
                "day": highlight(record.date.day if record.date else ""),
                "month": highlight(record.date.strftime("%B") if record.date else ""),
                "year": highlight(record.date.year if record.date else ""),
                "service_lines_table": record._render_service_lines_table(),
            }

            for var_name, value in vals.items():
                content = content.replace("{{" + var_name + "}}", value)

            # Clean up any {{partner_via}} placeholders (field removed from model)
            content = re.sub(
                r"\s*a\s+trav[ee]s\s+de\s+(<strong[^>]*>)?"
                r"\s*\{\{partner_via\}\}\s*(</strong>)?",
                "",
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                r"(<strong[^>]*>)?\s*\{\{partner_via\}\}"
                r"\s*(</strong>)?",
                "",
                content,
            )

            content = content.strip()
            record.content = Markup(content)

    def _render_lines_block(self, lines) -> str:
        """Render an HTML table for a list of service line records."""
        table_style = (
            "width: 100%; border-collapse: collapse; margin-top: 5px; "
            "font-family: Arial, sans-serif; font-size: 11px;"
        )
        th_style = (
            "border: 1px solid #000; padding: 4px; background-color: #f2f2f2; "
            "text-align: center; font-weight: bold;"
        )
        td_style = "border: 1px solid #000; padding: 4px; text-align: left;"
        td_num_style = "border: 1px solid #000; padding: 4px; text-align: right;"

        headers = [
            _("Producto/Servicio"),
            _("Descripción"),
            _("Cant."),
            _("UdM"),
            _("Precio Unitario"),
            _("Subtotal"),
            _("Límite Facturación"),
        ]

        rows = []
        for line in lines:
            deadline = (
                line.date_deadline_invoice.strftime("%d/%m/%Y")
                if line.date_deadline_invoice
                else ""
            )
            rows.append(
                f'<tr><td style="{td_style}">{line.product_id.name}</td>'
                f'<td style="{td_style}">{line.name}</td>'
                f'<td style="{td_num_style}">{line.quantity:.2f}</td>'
                f'<td style="{td_style}">{line.uom_id.name}</td>'
                f'<td style="{td_num_style}">{line.price_unit:,.2f}</td>'
                f'<td style="{td_num_style}">{line.price_subtotal:,.2f}</td>'
                f'<td style="{td_style}">{deadline}</td></tr>'
            )

        html = f'<table style="{table_style}"><thead><tr>'
        for header in headers:
            html += f'<th style="{th_style}">{header}</th>'
        html += "</tr></thead><tbody>"
        html += "".join(rows)
        html += "</tbody></table>"
        return html

    def _render_service_lines_table(self) -> str:
        """Render HTML tables for all service lines (general + per-UEB sections)."""
        parts = []

        if self.line_ids:
            parts.append(self._render_lines_block(self.line_ids))

        section_title_style = (
            "font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; "
            "margin-top: 12px; margin-bottom: 4px;"
        )
        for section in self.ueb_section_ids:
            if section.line_ids:
                ueb_name = section.ueb_id.name or ""
                parts.append(f'<p style="{section_title_style}">{ueb_name}</p>')
                parts.append(self._render_lines_block(section.line_ids))

        return "".join(parts)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("state"):
                vals["state"] = "borrador"
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "contrato.especifico.sequence",
                        sequence_date=fields.Date.context_today(self),
                    )
                    or "/"
                )
        return super().create(vals_list)

    def action_draft(self):
        """Revert to draft state."""
        for record in self:
            record.write({"state": "borrador"})

    def action_cancel(self):
        """Cancel the contract and all associated invoices."""
        for record in self:
            # General service lines
            lines = record.line_ids
            invoices = self.env["account.move"].search(
                [("service_line_id", "in", lines.ids)]
            )
            for inv in invoices:
                if inv.state == "posted":
                    inv.button_draft()
                if inv.state != "cancel":
                    inv.button_cancel()
            lines.with_context(is_uninvoice=True).write({"invoiced": False})

            # UEB section lines
            ueb_lines = record.ueb_section_ids.mapped("line_ids")
            if ueb_lines:
                ueb_invoices = self.env["account.move"].search(
                    [("ueb_service_line_id", "in", ueb_lines.ids)]
                )
                for inv in ueb_invoices:
                    if inv.state == "posted":
                        inv.button_draft()
                    if inv.state != "cancel":
                        inv.button_cancel()
                ueb_lines.with_context(is_uninvoice=True).write({"invoiced": False})

            record.write({"state": "cancelado"})

    def action_add_ueb_section(self) -> dict:
        """Open wizard to add a new UEB service line table to the contract."""
        self.ensure_one()
        return {
            "name": _("Agregar tabla de líneas de servicio por UEB"),
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico.add.ueb.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contrato_id": self.id},
        }

    def action_entregar(self):
        """Transition contract to signed state (final active state)."""
        for record in self:
            if record.state != "entregado":
                raise UserError(_("Solo se pueden firmar contratos entregados."))
            record.write({"state": "firmado"})

    def action_draft_from_entregado(self):
        """Revert contract from delivered back to draft."""
        for record in self:
            if record.state != "entregado":
                raise UserError(
                    _("Solo se puede retroceder a Borrador desde Entregado.")
                )
            record.write({"state": "borrador"})

    def action_sign(self):
        """Transition contract to delivered state."""
        for record in self:
            if record.state not in ["borrador", "cancelado", "firmado"]:
                raise UserError(
                    _(
                        "Only draft, cancelled, or signed contracts can be set to delivered."
                    )
                )
            if not record._has_generated_content():
                raise UserError(
                    _("Please generate the contract content before delivering.")
                )
            record.write({"state": "entregado"})

    def _has_generated_content(self) -> bool:
        self.ensure_one()
        if not self.content:
            return False

        plain_content = unescape(str(self.content or ""))
        plain_content = re.sub(r"<[^>]+>", " ", plain_content)
        plain_content = plain_content.replace("&nbsp;", " ")
        plain_content = re.sub(r"\s+", " ", plain_content).strip()
        return bool(plain_content)

    def action_facturar_todo(self) -> dict:
        """Invoice all uninvoiced service lines (general + UEB) of this contract."""
        self.ensure_one()

        if self.state != "firmado":
            raise UserError(
                _("Solo puede facturar un contrato que se encuentre Firmado.")
            )

        if not self.forma_pago_id:
            raise UserError(
                _(
                    "Debe configurar la Forma de Pago en los Datos de Facturación "
                    "del contrato antes de facturar."
                )
            )

        uninvoiced_lines = self.line_ids.filtered(lambda ln: not ln.invoiced)
        uninvoiced_ueb_lines = self.ueb_section_ids.mapped("line_ids").filtered(
            lambda ln: not ln.invoiced
        )

        if not uninvoiced_lines and not uninvoiced_ueb_lines:
            raise UserError(_("Todas las líneas de servicio ya han sido facturadas."))

        partner = self.partner_id
        base_vals: dict = {
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_date": fields.Date.today(),
            "contrato_especifico_id": self.id,
            "invoice_payment_term_id": self.forma_pago_id.id,
            "client_address": f"{partner.street or ''} {partner.city or ''}".strip(),
            "client_nit": getattr(partner, "tax_id", None) or partner.vat or "",
            "client_bank_account": getattr(partner, "bank_account_cup", None) or "",
            "realizada_por_id": self.realizada_por_id.id
            if self.realizada_por_id
            else False,
        }

        for line in uninvoiced_lines:
            line._apply_default_invoice_dates()
            self.env["account.move"].create(
                {
                    **base_vals,
                    "service_line_id": line.id,
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
                }
            )
            line.with_context(is_uninvoice=True).write({"invoiced": True})

        for line in uninvoiced_ueb_lines:
            line._apply_default_invoice_dates()
            self.env["account.move"].create(
                {
                    **base_vals,
                    "ueb_service_line_id": line.id,
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
                }
            )
            line.with_context(is_uninvoice=True).write({"invoiced": True})

        return self.action_view_invoices()
