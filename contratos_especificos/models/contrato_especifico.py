import re

from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContratoEspecifico(models.Model):
    _name = "contrato.especifico"
    _description = "Specific Contract"
    _order = "name desc"

    name = fields.Char(string="Contract Number", required=True)
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
        domain="[('is_company', '=', False), ('company_id', '=', company_id)]",
    )
    our_rep_decision_number = fields.Char(string="Our Rep. Decision Number")
    our_rep_decision_date = fields.Date(string="Our Rep. Decision Date")
    our_project_leader_id = fields.Many2one(
        "res.partner",
        string="Líder del Proyecto Nuestro",
        domain="[('is_company', '=', False), ('company_id', '=', company_id)]",
    )
    project_leader = fields.Char(string="Líder del Proyecto del Cliente")
    application_name = fields.Char(string="Nombre de la Aplicación")

    def write(self, vals):
        """Prevent editing signed contracts."""
        for record in self:
            if record.state == "firmado" and not self.env.su:
                # Allow changing state (e.g., to cancel or draft) but nothing else
                if not (len(vals) == 1 and "state" in vals):
                    raise UserError(
                        _("No puede modificar un contrato que ya está firmado.")
                    )
        return super().write(vals)

    template_type_requires_rep = fields.Boolean(
        compute="_compute_template_type_flags",
        store=False,
    )
    template_type_requires_leader = fields.Boolean(
        compute="_compute_template_type_flags",
        store=False,
    )
    template_type_requires_app = fields.Boolean(
        compute="_compute_template_type_flags",
        store=False,
    )

    date = fields.Date(
        string="Contract Subscription Date",
        default=fields.Date.context_today,
    )
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")

    state = fields.Selection(
        [
            ("borrador", "Draft"),
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

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "The Contract Number must be unique. A specific contract "
            "with this number already exists.",
        )
    ]

    @api.depends("template_id", "template_id.type")
    def _compute_template_type_flags(self):
        for record in self:
            t = record.template_id.type if record.template_id else False
            record.template_type_requires_rep = t in (
                "cgm_disponibilidad",
                "productos_soporte",
            )
            record.template_type_requires_leader = t == "versat_iniciales"
            record.template_type_requires_app = t in (
                "productos_soporte",
                "soporte_desarrollo",
            )

    @api.onchange("marco_id")
    def _onchange_marco_id(self):
        if self.marco_id:
            self.our_representative_id = self.marco_id.our_representative_id
            self.our_rep_decision_number = self.marco_id.our_rep_decision_number
            self.our_rep_decision_date = self.marco_id.our_rep_decision_date

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
                "marco_date": fmt_date(marco.date),
                "our_representative": highlight(our_r.name if our_r else ""),
                "our_rep_function": highlight(our_r.function if our_r else ""),
                "our_rep_decision_number": highlight(record.our_rep_decision_number),
                "partner_name": highlight(p.name),
                "partner_via": (highlight(marco.oeb) if marco.oeb else ""),
                "partner_short_name": highlight(p.short_name),
                "project_leader": highlight(record.project_leader),
                "application_name": highlight(record.application_name),
                "start_date": fmt_date(record.start_date),
                "day": highlight(record.date.day if record.date else ""),
                "month": highlight(record.date.strftime("%B") if record.date else ""),
                "year": highlight(record.date.year if record.date else ""),
                "service_lines_table": record._render_service_lines_table(),
            }

            for var_name, value in vals.items():
                if var_name == "partner_via" and not marco.oeb:
                    continue
                content = content.replace("{{" + var_name + "}}", value)

            if not marco.oeb:
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

    def _render_service_lines_table(self):
        """Render an HTML table for the service lines."""
        if not self.line_ids:
            return ""

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
            _("Service/Product"),
            _("Description"),
            _("Qty"),
            _("UoM"),
            _("Unit Price (CUP)"),
            _("Amount"),
            _("Deadline"),
        ]

        rows = []
        for line in self.line_ids:
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("state"):
                vals["state"] = "borrador"
        return super().create(vals_list)

    def action_draft(self):
        """Revert to draft state."""
        for record in self:
            record.write({"state": "borrador"})

    def action_cancel(self):
        """Cancel the contract and all associated invoices."""
        for record in self:
            # Find all invoices linked to this contract's lines
            lines = record.line_ids
            invoices = self.env["account.move"].search(
                [("service_line_id", "in", lines.ids)]
            )
            for inv in invoices:
                if inv.state == "posted":
                    inv.button_draft()
                if inv.state != "cancel":
                    inv.button_cancel()

            # Reset the invoiced flag on lines
            lines.with_context(is_uninvoice=True).write({"invoiced": False})

            record.write({"state": "cancelado"})

    def action_sign(self):
        """Transition contract to signed state."""
        for record in self:
            if record.state not in ["borrador", "cancelado"]:
                raise UserError(_("Only draft or cancelled contracts can be signed."))
            if not record.content:
                raise UserError(
                    _("Please generate the contract content before signing.")
                )
            record.write({"state": "firmado"})
