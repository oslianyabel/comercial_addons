import re
from datetime import date as pydate
from html import unescape

from markupsafe import Markup

from odoo import _, api, fields, models

# Labels shown in the changed-fields summary
_FIELD_LABELS: dict[str, str] = {
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


class ContratoEspecificoSuplemento(models.Model):
    _name = "contrato.especifico.suplemento"
    _description = "Suplemento de Contrato Específico"
    _order = "sequence_number desc"

    # ── Identificación y versioning ──────────────────────────────────────────

    name = fields.Char(
        string="Número de Suplemento",
        required=True,
        default="/",
        readonly=True,
        copy=False,
    )
    contrato_id = fields.Many2one(
        "contrato.especifico",
        string="Contrato Específico Original",
        required=True,
        ondelete="restrict",
        readonly=True,
    )
    sequence_number = fields.Integer(
        string="Nº de Versión",
        required=True,
        readonly=True,
        copy=False,
    )
    modified_by_id = fields.Many2one(
        "res.users",
        string="Modificado por",
        readonly=True,
        copy=False,
    )
    modification_date = fields.Datetime(
        string="Fecha de Modificación",
        readonly=True,
        copy=False,
    )
    modificaciones = fields.Text(
        string="Modificaciones",
        copy=False,
    )

    # ── Datos copiados del contrato ───────────────────────────────────────────

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        related="contrato_id.company_id",
        store=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        related="contrato_id.partner_id",
        store=True,
    )
    contract_type = fields.Selection(
        related="contrato_id.contract_type",
        string="Tipo de Contrato del Marco",
        store=True,
    )
    marco_id = fields.Many2one(
        "contrato.marco",
        string="Contrato Marco",
        readonly=True,
    )
    suplemento_marco_id = fields.Many2one(
        "contrato.suplemento",
        string="Suplemento del Marco",
        readonly=True,
    )
    template_id = fields.Many2one(
        "contrato.especifico.template",
        string="Tipo de Contrato",
    )
    our_representative_id = fields.Many2one(
        "res.partner",
        string="Nuestro Representante",
        related="contrato_id.our_representative_id",
        readonly=True,
    )
    our_rep_decision_number = fields.Char(
        string="Acuerdo/Resolución",
        related="contrato_id.our_rep_decision_number",
        readonly=True,
    )
    our_rep_decision_date = fields.Date(
        string="Fecha de Resolución",
        related="contrato_id.our_rep_decision_date",
        readonly=True,
    )
    our_project_leader_id = fields.Many2one(
        "res.partner",
        string="Líder del Proyecto Nuestro",
    )
    project_leader_id = fields.Many2one(
        "res.partner",
        string="Líder del Proyecto del Cliente",
    )
    application_name = fields.Char(string="Nombre de la Aplicación")

    date = fields.Date(string="Fecha de Suscripción")
    validity_years = fields.Integer(string="Vigencia (años)")
    start_date = fields.Date(string="Fecha de Entrada en Vigor")
    end_date = fields.Date(
        string="Fecha de Finalización",
        compute="_compute_end_date",
        store=True,
    )
    content = fields.Html(string="Contenido del Contrato")

    forma_pago_id = fields.Many2one("account.payment.term", string="Forma de Pago")
    realizada_por_id = fields.Many2one("res.partner", string="Realizada por")
    transportado_por_id = fields.Many2one("res.partner", string="Transportado por")
    recibido_por_id = fields.Many2one("res.partner", string="Recibido por")
    entregada_por_id = fields.Many2one("res.partner", string="Entregada por")
    contabilizada_por_id = fields.Many2one("res.partner", string="Contabilizada por")

    # Flags de template (sin store para no requerir recompute write)
    template_type_requires_rep = fields.Boolean(
        compute="_compute_template_type_flags",
        store=False,
    )
    template_type_requires_application_name = fields.Boolean(
        compute="_compute_template_type_flags",
        store=False,
    )

    line_ids = fields.One2many(
        "contrato.especifico.suplemento.line",
        "suplemento_id",
        string="Líneas de Servicio",
    )
    ueb_section_ids = fields.One2many(
        "contrato.especifico.suplemento.ueb.section",
        "suplemento_id",
        string="Secciones UEB",
    )

    # ── Constrains y computed ─────────────────────────────────────────────────

    @api.depends("start_date", "validity_years")
    def _compute_end_date(self) -> None:
        for record in self:
            if record.start_date and record.validity_years:
                record.end_date = self._add_years(
                    record.start_date, record.validity_years
                )
            else:
                record.end_date = False

    @api.depends("template_id", "template_id.type")
    def _compute_template_type_flags(self) -> None:
        for record in self:
            t = record.template_id.type if record.template_id else False
            record.template_type_requires_rep = t in (
                "cgm_disponibilidad",
                "productos_soporte",
            )
            record.template_type_requires_application_name = t in (
                "productos_soporte",
                "soporte_desarrollo",
            )

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

    # ── ORM overrides ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> "ContratoEspecificoSuplemento":
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "/":
                contrato_name = "/"
                if vals.get("contrato_id"):
                    contrato = self.env["contrato.especifico"].browse(
                        vals["contrato_id"]
                    )
                    contrato_name = contrato.name or "/"
                seq = vals.get("sequence_number", 1)
                vals["name"] = f"SUP_{seq:02d}_{contrato_name}"
        return super().create(vals_list)

    # ── Generación de contenido ───────────────────────────────────────────────

    def action_generate_content(self) -> None:
        for record in self:
            if not record.template_id or not record.template_id.content:
                raise UserError(
                    _("Seleccione un tipo de contrato con contenido antes de generar.")
                )

            content = unescape(str(record.template_id.content or ""))
            p = record.partner_id
            marco = record.marco_id
            our_r = record.our_representative_id

            missing: list[str] = []
            if not our_r:
                missing.append(_("Nuestro Representante"))
            if not marco:
                missing.append(_("Contrato Marco"))
            if (
                record.template_type_requires_application_name
                and not record.application_name
            ):
                missing.append(_("Nombre de la Aplicación"))

            if missing:
                raise UserError(
                    _(
                        "No se puede generar el contenido porque faltan los siguientes datos:\n\n- %s"
                    )
                    % "\n- ".join(missing)
                )

            def highlight(val: object) -> str:
                return (
                    '<strong style="font-weight: bold; text-decoration: '
                    'underline; color: #000080;">' + str(val or "") + "</strong>"
                )

            def fmt_date(d) -> str:
                return (
                    highlight(d.strftime("%d/%m/%Y"))
                    if d
                    else highlight("__________________")
                )

            template_vals = {
                "specific_number": highlight(record.name),
                "marco_number": highlight(marco.name),
                "marco_date": fmt_date(
                    record.suplemento_marco_id.start_date
                    if record.suplemento_marco_id
                    else marco.start_date
                ),
                "our_representative": highlight(our_r.name if our_r else ""),
                "our_rep_function": highlight(our_r.function if our_r else ""),
                "our_rep_decision_number": highlight(record.our_rep_decision_number),
                "partner_name": highlight(p.name if p else ""),
                "partner_short_name": highlight(p.short_name if p else ""),
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

            for var_name, value in template_vals.items():
                content = content.replace("{{" + var_name + "}}", value)

            content = re.sub(
                r"\s*a\s+trav[ee]s\s+de\s+(<strong[^>]*>)?"
                r"\s*\{\{partner_via\}\}\s*(</strong>)?",
                "",
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                r"(<strong[^>]*>)?\s*\{\{partner_via\}\}\s*(</strong>)?",
                "",
                content,
            )

            content = content.strip()
            # bypass_suplemento_write para evitar que el write() intercepte
            record.with_context(bypass_suplemento_write=True).write(
                {"content": Markup(content)}
            )

    # ── Renderizado de líneas ─────────────────────────────────────────────────

    def _render_lines_block(self, lines) -> str:
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
        parts: list[str] = []

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

    # ── Acciones ──────────────────────────────────────────────────────────────

    def action_open_contrato_original(self) -> dict:
        self.ensure_one()
        return {
            "name": _("Contrato Específico Original"),
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico",
            "view_mode": "form",
            "res_id": self.contrato_id.id,
        }
