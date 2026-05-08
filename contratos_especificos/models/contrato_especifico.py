import logging
import re
from datetime import date as pydate
from html import unescape

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class ContratoEspecifico(models.Model):
    _name = "contrato.especifico"
    _description = "Specific Contract"
    _order = "name desc"

    name = fields.Char(string="Contract Number", required=True, default="/")
    marco_id = fields.Many2one(
        "contrato.marco",
        string="Master Contract",
        domain=[("state", "=", "firmado")],
    )
    suplemento_id = fields.Many2one(
        "contrato.suplemento",
        string="Suplemento",
        domain="[('state', '=', 'firmado'), ('marco_id', '=', marco_id)]",
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
        [
            "state",
            "service_line_state",
            "invoice_count",
            "end_date",
            "motivo_cancelacion",
        ]
    )

    suplemento_especifico_ids = fields.One2many(
        "contrato.especifico.suplemento",
        "contrato_id",
        string="Suplementos",
    )
    suplemento_especifico_count = fields.Integer(
        string="Nº Suplementos",
        compute="_compute_suplemento_especifico_count",
    )
    amount_pending_invoice = fields.Float(
        string="Por Facturar",
        compute="_compute_amount_pending_invoice",
        store=True,
    )

    @api.depends("suplemento_especifico_ids")
    def _compute_suplemento_especifico_count(self) -> None:
        for record in self:
            record.suplemento_especifico_count = len(record.suplemento_especifico_ids)

    @api.depends(
        "line_ids.price_subtotal",
        "line_ids.invoiced",
        "line_ids.is_invoice_line",
        "ueb_section_ids.line_ids.price_subtotal",
        "ueb_section_ids.line_ids.invoiced",
        "ueb_section_ids.line_ids.is_invoice_line",
    )
    def _compute_amount_pending_invoice(self) -> None:
        for record in self:
            general = sum(
                ln.price_subtotal
                for ln in record.line_ids
                if not ln.invoiced and not ln.is_invoice_line
            )
            ueb = sum(
                ln.price_subtotal
                for section in record.ueb_section_ids
                for ln in section.line_ids
                if not ln.invoiced and not ln.is_invoice_line
            )
            record.amount_pending_invoice = general + ueb

    def write(self, vals):
        """Intercepts writes on signed contracts to create suplementos automatically.

        - Signed contracts: creates a suplemento with the new values; original stays unchanged.
        - Non-signed contracts: normal write.
        - ORM-managed system fields (state, end_date, …) always go through.
        """
        if not self.env.su:
            blocked_keys = vals.keys() - self._SYSTEM_WRITE_ALLOWED
            if blocked_keys:
                firmado_records = self.filtered(lambda r: r.state == "firmado")
                if firmado_records:
                    for record in firmado_records:
                        record._create_suplemento_from_vals(vals)
                    non_firmado = self - firmado_records
                    if non_firmado:
                        super(ContratoEspecifico, non_firmado).write(vals)
                    return True
        return super().write(vals)

    def _create_suplemento_from_vals(self, vals: dict) -> None:
        """Creates a new suplemento from the current firmado contract applying the provided vals.

        Does NOT modify the original contract.
        """
        self.ensure_one()

        sequence_number = len(self.suplemento_especifico_ids) + 1

        # Build the new state: current values + incoming changes
        sup_vals: dict = {
            "contrato_id": self.id,
            "sequence_number": sequence_number,
            "modified_by_id": self.env.user.id,
            "modification_date": fields.Datetime.now(),
            "marco_id": self.marco_id.id if self.marco_id else False,
            "suplemento_marco_id": self.suplemento_id.id
            if self.suplemento_id
            else False,
            "template_id": self.template_id.id if self.template_id else False,
            "our_project_leader_id": (
                self.our_project_leader_id.id if self.our_project_leader_id else False
            ),
            "project_leader_id": (
                self.project_leader_id.id if self.project_leader_id else False
            ),
            "application_name": self.application_name,
            "date": self.date,
            "validity_years": self.validity_years,
            "start_date": self.start_date,
            "content": self.content,
            "forma_pago_id": self.forma_pago_id.id if self.forma_pago_id else False,
            "realizada_por_id": (
                self.realizada_por_id.id if self.realizada_por_id else False
            ),
            "transportado_por_id": (
                self.transportado_por_id.id if self.transportado_por_id else False
            ),
            "recibido_por_id": (
                self.recibido_por_id.id if self.recibido_por_id else False
            ),
            "entregada_por_id": (
                self.entregada_por_id.id if self.entregada_por_id else False
            ),
            "contabilizada_por_id": (
                self.contabilizada_por_id.id if self.contabilizada_por_id else False
            ),
        }

        # Apply incoming changes (Many2one fields arrive as IDs in vals)
        scalar_fields = {
            k: v for k, v in vals.items() if k not in ("line_ids", "ueb_section_ids")
        }
        sup_vals.update(scalar_fields)

        # Build modificaciones (comma-separated list of changed field labels)
        sup_vals["modificaciones"] = self._build_modificaciones(vals)

        # Prepend "SUPLEMENTO AL " to the first contract title in the content
        raw_content = str(sup_vals.get("content") or "")
        if raw_content:
            modified = re.sub(
                r"(CONTRATO\s+(?:ESPECÍFICO|MARCO))",
                r"SUPLEMENTO AL \1",
                raw_content,
                count=1,
            )
            sup_vals["content"] = Markup(modified)

        sup = self.env["contrato.especifico.suplemento"].create(sup_vals)

        # Copy service lines (apply ORM commands if present)
        line_commands = vals.get("line_ids")
        invoiced_ids = frozenset(self.line_ids.filtered("invoiced").ids)
        lines_data = self._resolve_line_snapshot(
            self.line_ids, line_commands, invoiced_ids
        )
        SupLine = self.env["contrato.especifico.suplemento.line"]
        for data in lines_data:
            SupLine.create({"suplemento_id": sup.id, **data})

        # Copy UEB sections
        ueb_commands = vals.get("ueb_section_ids")
        for section in self.ueb_section_ids:
            new_section = self.env["contrato.especifico.suplemento.ueb.section"].create(
                {
                    "suplemento_id": sup.id,
                    "ueb_id": section.ueb_id.id,
                    "sequence": section.sequence,
                }
            )
            SupUebLine = self.env["contrato.especifico.suplemento.ueb.line"]
            # Resolve UEB line changes from commands targeting this section
            ueb_section_commands = self._extract_ueb_section_commands(
                ueb_commands, section.id
            )
            ueb_invoiced_ids = frozenset(section.line_ids.filtered("invoiced").ids)
            ueb_lines_data = self._resolve_line_snapshot(
                section.line_ids, ueb_section_commands, ueb_invoiced_ids
            )
            for data in ueb_lines_data:
                data.pop("date_deadline_invoice", None)
                SupUebLine.create({"section_id": new_section.id, **data})

        _logger.info(
            "Suplemento %s creado automáticamente sobre contrato %s por %s.",
            sup.name,
            self.name,
            self.env.user.name,
        )

        # Redirigir al usuario al suplemento recién creado
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "contrato_especifico_suplemento_creado",
            {
                "suplemento_id": sup.id,
                "suplemento_name": sup.name,
            },
        )

    def _build_modificaciones(self, vals: dict) -> str:
        """Returns a comma-separated list of human-readable labels for the changed fields."""
        LABELS: dict[str, str] = {
            "template_id": "Tipo de Contrato",
            "our_project_leader_id": "Líder del Proyecto Nuestro",
            "project_leader_id": "Líder del Proyecto del Cliente",
            "application_name": "Nombre de la Aplicación",
            "date": "Fecha de Suscripción",
            "validity_years": "Vigencia (años)",
            "start_date": "Fecha de Entrada en Vigor",
            "content": "Contenido del Contrato",
            "forma_pago_id": "Forma de Pago",
            "realizada_por_id": "Realizada por",
            "transportado_por_id": "Transportado por",
            "recibido_por_id": "Recibido por",
            "entregada_por_id": "Entregada por",
            "contabilizada_por_id": "Contabilizada por",
            "line_ids": "Líneas de Servicio",
            "ueb_section_ids": "Secciones UEB",
        }

        changed: list[str] = [label for key, label in LABELS.items() if key in vals]
        return ", ".join(changed) if changed else ""

    @staticmethod
    def _resolve_line_snapshot(
        current_lines, commands, invoiced_ids: frozenset | None = None
    ) -> list[dict]:
        """Applies ORM commands against current lines and returns a list of field dicts.

        If invoiced_ids is provided, quantity and price_unit are preserved for those line IDs.
        """
        COPYABLE = [
            "product_id",
            "name",
            "quantity",
            "uom_id",
            "price_unit",
            "date_deadline_invoice",
            "start_date",
            "end_date",
        ]
        PROTECTED_INVOICED = {"quantity", "price_unit"}

        def _line_to_dict(line) -> dict:
            return {
                "product_id": line.product_id.id if line.product_id else False,
                "name": line.name,
                "quantity": line.quantity,
                "uom_id": line.uom_id.id if line.uom_id else False,
                "price_unit": line.price_unit,
                "date_deadline_invoice": getattr(line, "date_deadline_invoice", False),
                "start_date": getattr(line, "start_date", False),
                "end_date": getattr(line, "end_date", False),
                "original_invoiced": getattr(line, "invoiced", False),
            }

        lines_by_id: dict[int, dict] = {
            line.id: _line_to_dict(line) for line in current_lines
        }
        result_ids: list[int] = list(lines_by_id.keys())
        extra: list[dict] = []

        if not commands:
            return list(lines_by_id.values())

        for cmd in commands:
            code = cmd[0]
            if code == 0:  # CREATE
                data = {k: v for k, v in cmd[2].items() if k in COPYABLE}
                extra.append(data)
            elif code == 1:  # UPDATE
                if cmd[1] in lines_by_id:
                    update_data = {k: v for k, v in cmd[2].items() if k in COPYABLE}
                    if invoiced_ids and cmd[1] in invoiced_ids:
                        for f in PROTECTED_INVOICED:
                            update_data.pop(f, None)
                    lines_by_id[cmd[1]].update(update_data)
            elif code in (2, 3):  # DELETE / UNLINK
                result_ids = [i for i in result_ids if i != cmd[1]]
            elif code == 5:  # CLEAR
                result_ids = []
            elif code == 6:  # SET
                result_ids = [i for i in cmd[2] if i in lines_by_id]

        return [lines_by_id[i] for i in result_ids if i in lines_by_id] + extra

    @staticmethod
    def _extract_ueb_section_commands(ueb_commands, section_id: int) -> list | None:
        """Extracts line commands for a specific UEB section from ueb_section_ids commands."""
        if not ueb_commands:
            return None
        for cmd in ueb_commands:
            if cmd[0] == 1 and cmd[1] == section_id and "line_ids" in cmd[2]:
                return cmd[2]["line_ids"]
        return None

    def action_open_suplementos_especificos(self) -> dict:
        self.ensure_one()
        return {
            "name": _("Suplementos de %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico.suplemento",
            "view_mode": "tree,form",
            "domain": [("contrato_id", "=", self.id)],
            "context": {"default_contrato_id": self.id},
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
    motivo_cancelacion = fields.Text(
        string="Motivo de Cancelación",
        copy=False,
        readonly=True,
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

    @api.onchange("suplemento_id")
    def _onchange_suplemento_id(self) -> None:
        if self.suplemento_id:
            self.marco_id = self.suplemento_id.marco_id

    @api.onchange("marco_id")
    def _onchange_marco_id(self) -> None:
        """Limpia suplemento_id si ya no pertenece al marco seleccionado."""
        if self.suplemento_id and self.suplemento_id.marco_id != self.marco_id:
            self.suplemento_id = False

    @api.constrains("marco_id", "suplemento_id")
    def _check_marco_or_suplemento(self) -> None:
        for record in self:
            if not record.marco_id and not record.suplemento_id:
                raise ValidationError(
                    _("Debe seleccionar un Contrato Marco o un Suplemento firmado.")
                )
            if (
                record.suplemento_id
                and record.marco_id
                and record.marco_id != record.suplemento_id.marco_id
            ):
                raise ValidationError(
                    _(
                        "El Contrato Marco debe corresponder al marco del "
                        "Suplemento seleccionado."
                    )
                )

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
                "marco_date": fmt_date(
                    record.suplemento_id.start_date
                    if record.suplemento_id
                    else marco.start_date
                ),
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
        """Open cancellation wizard."""
        self.ensure_one()
        return {
            "name": _("Confirmar Cancelación"),
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contrato_id": self.id},
        }

    def action_cancel_confirmed(self, motivo: str) -> None:
        """Cancel the contract with the given reason and cancel all associated invoices."""
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
            record.write({"motivo_cancelacion": motivo})

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

        uninvoiced_lines = self.line_ids.filtered(
            lambda ln: not ln.invoiced and not ln.is_invoice_line
        )
        uninvoiced_ueb_lines = self.ueb_section_ids.mapped("line_ids").filtered(
            lambda ln: not ln.invoiced and not ln.is_invoice_line
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
