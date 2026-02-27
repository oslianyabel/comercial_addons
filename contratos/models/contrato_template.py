import os
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContratoTemplate(models.Model):
    _name = "contrato.template"
    _description = "Contract Template"
    _order = "id"

    name = fields.Char(string="Name", required=True)
    type = fields.Selection(
        [("mipyme", "MiPyme"), ("tcp", "TCP"), ("empresa", "Empresa")],
        string="Contract Type",
        required=True,
    )
    content = fields.Html(string="Template Content", required=True)
    active = fields.Boolean(string="Active", default=True)

    # Sync Tracking
    last_sync_date = fields.Datetime(string="Last Sync from Filesystem")
    sync_state = fields.Selection(
        [("synced", _("Synced")), ("modified", _("Modified"))],
        string="Sync Status",
        compute="_compute_sync_state",
        store=True,
    )

    available_variables = fields.Text(
        string="Available Variables",
        compute="_compute_available_variables",
        help="List of variables that you can use in this template.",
    )

    _sql_constraints = [
        (
            "type_unique",
            "UNIQUE(type)",
            "A template for this contract type already exists.",
        )
    ]

    def _compute_available_variables(self):
        common = [
            "contract_number",
            "our_email",
            "our_representative",
            "our_rep_decision_number",
            "our_rep_decision_date",
            "partner_name",
            "partner_via",
            "partner_oeb",
            "partner_short_name",
            "partner_organism",
            "partner_resolution_number",
            "partner_creation_date",
            "partner_issued_by",
            "partner_address",
            "partner_reeup",
            "partner_bank_account_cup",
            "partner_bank_branch",
            "partner_bank_name",
            "partner_bank_address",
            "partner_titular",
            "partner_phone",
            "partner_email",
            "partner_tax_id",
            "partner_representative",
            "partner_rep_function",
            "partner_current_resolution",
            "partner_current_date",
            "partner_current_issued_by",
            "day",
            "month",
            "year",
        ]
        mipyme_extra = [
            "notary_deed_number",
            "mercantile_register",
            "register_volume",
            "register_page",
            "register_sheet",
            "bank_account_mlc",
            "bank_mlc_branch",
            "partner_bank_municipality",
            "partner_bank_province",
            "partner_appointed_by_agreement",
            "partner_appointment_date",
        ]
        tcp_extra = [
            "id_card",
            "partner_municipality",
            "partner_province",
            "partner_issued_by_location",
            "partner_bank_name_mlc",
            "tcp_bank_mlc_branch",
            "partner_bank_address_mlc",
            "partner_bank_municipality_mlc",
            "partner_bank_province_mlc",
            "partner_bank_name_cup",
            "tcp_bank_cup_branch",
            "partner_bank_address_cup",
            "partner_bank_municipality_cup",
            "partner_bank_province_cup",
        ]
        for record in self:
            vars_list = common.copy()
            if record.type == "mipyme":
                vars_list += mipyme_extra
            elif record.type == "tcp":
                vars_list += tcp_extra

            record.available_variables = "\n".join([f"{{{{{v}}}}}" for v in vars_list])

    def _get_base_path(self):
        """Automatically detect the context directory relative to this file."""
        # This file is in: extra_addons/contratos/models/contrato_template.py
        # We need: extra_addons/context
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up 2 levels: models -> contratos -> extra_addons
        extra_addons_path = os.path.abspath(os.path.join(current_dir, "..", ".."))
        return os.path.join(extra_addons_path, "context")

    def _get_filesystem_content(self):
        """Helper to get and format the current filesystem content for comparison."""
        base_path = self._get_base_path()
        templates = {
            "mipyme": "contrato marco Mipyme",
            "tcp": "contrato marco TCP.txt",
            "empresa": "contrato marco empresas.txt",
        }
        filename = templates.get(self.type)
        if filename:
            template_path = os.path.join(base_path, filename)
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    raw_content = f.read()
                    return self._format_to_html(raw_content)
        return False

    @api.depends("content", "last_sync_date")
    def _compute_sync_state(self):
        for record in self:
            fs_content = record._get_filesystem_content()
            if fs_content and self._prepare_for_comparison(
                record.content
            ) == self._prepare_for_comparison(fs_content):
                record.sync_state = "synced"
            else:
                record.sync_state = "modified"

    def _prepare_for_comparison(self, html):
        """Standardize HTML for comparison by removing all formatting noise, attributes and whitespace."""
        if not html:
            return ""
        # Remove all attributes from tags
        res = re.sub(r"<(\w+)[^>]*>", r"<\1>", html)
        # Lowercase everything
        res = res.lower()
        # Remove all whitespaces and newlines
        res = re.sub(r"\s+", "", res)
        # Remove non-breaking spaces
        res = res.replace("&nbsp;", "")
        return res

    def unlink(self):
        """Allow deleting duplicates but protect the last remaining template of each type."""
        for record in self:
            others = self.search([("type", "=", record.type), ("id", "!=", record.id)])
            if not others:
                raise UserError(
                    _("You cannot delete the last template for %s. It is required.")
                    % dict(self._fields["type"].selection).get(record.type)
                )
        return super().unlink()

    @api.model
    def _format_to_html(self, raw_content):
        """Standardized logic to convert plain text contract to Odoo-friendly HTML."""
        if not raw_content:
            return ""

        # Stricter detection of complex HTML.
        has_block_tags = re.search(
            r"<(p|div|h1|h2|h3|table|br|ul|ol|li)", raw_content, re.IGNORECASE
        )

        if not has_block_tags:
            lineas = raw_content.splitlines()
            formatted_lineas = []
            for idx, linea in enumerate(lineas):
                linea = linea.strip()
                if not linea:
                    formatted_lineas.append(
                        '<p style="margin-bottom: 20px; line-height: 1.6;">&nbsp;</p>'
                    )
                    continue

                is_header = len(linea) < 120 and (
                    linea.isupper() or "CLÁUSULA" in linea.upper() or idx == 0
                )

                if is_header:
                    font_size = "18px" if idx == 0 else "16px"
                    formatted_lineas.append(
                        f'<h2 style="text-align: center; font-weight: bold; font-size: {font_size}; margin-top: 30px; margin-bottom: 15px;">{linea}</h2>'
                    )
                else:
                    formatted_lineas.append(
                        f'<p style="text-align: justify; margin-bottom: 20px; line-height: 1.6;">{linea}</p>'
                    )
            raw_content = "".join(formatted_lineas)
        else:
            # Handle standard double newline to spacing if it's already semi-HTML
            raw_content = raw_content.replace(
                "\n\n",
                '</p><p style="margin-bottom: 20px;">&nbsp;</p><p style="margin-bottom: 20px; text-align: justify; line-height: 1.6;">',
            )

        # Bold variables {{variable}}
        # We wrap them in <strong> tags while ensuring we don't double-wrap if already HTML
        raw_content = re.sub(
            r"\{\{([^{}]+)\}\}", r"<strong>{{\1}}</strong>", raw_content
        )

        return raw_content

    @api.model
    def _get_required_variables(self, template_type):
        """Hardcoded list of variables that MUST be present in each template type."""
        common = [
            "contract_number",
            "our_email",
            "our_representative",
            "our_rep_decision_number",
            "our_rep_decision_date",
            "partner_name",
            "partner_address",
            "partner_tax_id",
            "partner_email",
            "day",
            "month",
            "year",
        ]
        if template_type == "mipyme":
            return common + [
                "notary_deed_number",
                "mercantile_register",
                "register_volume",
                "register_page",
                "register_sheet",
                "partner_reeup",
                "partner_phone",
                "partner_bank_account_cup",
                "partner_titular",
                "partner_bank_branch",
                "partner_bank_name",
                "partner_bank_address",
                "partner_bank_municipality",
                "partner_bank_province",
                "bank_account_mlc",
                "bank_mlc_branch",
                "partner_representative",
                "partner_rep_function",
                "partner_appointed_by_agreement",
                "partner_appointment_date",
            ]
        elif template_type == "tcp":
            return common + [
                "id_card",
                "partner_municipality",
                "partner_province",
                "partner_issued_by_location",
                "bank_account_mlc",
                "partner_bank_name_mlc",
                "tcp_bank_mlc_branch",
                "partner_bank_address_mlc",
                "partner_bank_municipality_mlc",
                "partner_bank_province_mlc",
                "bank_account_cup",
                "partner_bank_name_cup",
                "tcp_bank_cup_branch",
                "partner_bank_address_cup",
                "partner_bank_municipality_cup",
                "partner_bank_province_cup",
            ]
        elif template_type == "empresa":
            return common + [
                "partner_short_name",
                "partner_organism",
                "partner_resolution_number",
                "partner_creation_date",
                "partner_issued_by",
                "partner_reeup",
                "partner_bank_account_cup",
                "partner_bank_branch",
                "partner_bank_name",
                "partner_bank_address",
                "partner_titular",
                "partner_phone",
                "partner_representative",
                "partner_rep_function",
                "partner_current_resolution",
                "partner_current_date",
                "partner_current_issued_by",
            ]
        return common

    def _validate_content_variables(self, content, template_type):
        """Check if all required variables are present in the provided content."""
        if not content:
            return
        required = self._get_required_variables(template_type)
        missing = []
        for var in required:
            pattern = r"\{\{\s*%s\s*\}\}" % re.escape(var)
            if not re.search(pattern, content):
                missing.append(f"{{{{{var}}}}}")

        if missing:
            raise UserError(
                _(
                    "The template content is missing the following required variables: %s. "
                    "These are necessary for correct contract generation."
                )
                % ", ".join(missing)
            )

    def write(self, vals):
        """Validate variables if content is updated."""
        if "content" in vals:
            for record in self:
                self._validate_content_variables(
                    vals["content"], vals.get("type", record.type)
                )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Validate variables on creation."""
        for vals in vals_list:
            if "content" in vals and "type" in vals:
                self._validate_content_variables(vals["content"], vals["type"])
        return super().create(vals_list)

    def action_import_from_filesystem(self):
        """Utility to force import/overwrite all templates from the known filesystem path."""
        base_path = self._get_base_path()
        templates = {
            "mipyme": "contrato marco Mipyme",
            "tcp": "contrato marco TCP.txt",
            "empresa": "contrato marco empresas.txt",
        }

        count = 0
        now = fields.Datetime.now()
        for c_type, filename in templates.items():
            template_path = os.path.join(base_path, filename)
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    raw_content = f.read()
                    if raw_content:
                        # Validate before applying
                        self._validate_content_variables(raw_content, c_type)

                        html_content = self._format_to_html(raw_content)
                        existing = self.search([("type", "=", c_type)], limit=1)
                        if existing:
                            existing.write(
                                {
                                    "content": html_content,
                                    "last_sync_date": now,
                                }
                            )
                        else:
                            self.create(
                                {
                                    "name": filename.replace(".txt", "").capitalize(),
                                    "type": c_type,
                                    "content": html_content,
                                    "last_sync_date": now,
                                }
                            )
                        count += 1
        return self._notify_import(count)

    def action_reset_from_filesystem(self):
        """Force overwrite this template with the content from the filesystem."""
        base_path = self._get_base_path()
        templates = {
            "mipyme": "contrato marco Mipyme",
            "tcp": "contrato marco TCP.txt",
            "empresa": "contrato marco empresas.txt",
        }
        filename = templates.get(self.type)
        if filename:
            template_path = os.path.join(base_path, filename)
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    raw_content = f.read()
                    if raw_content:
                        # Validate before applying
                        self._validate_content_variables(raw_content, self.type)

                        self.write(
                            {
                                "content": self._format_to_html(raw_content),
                                "last_sync_date": fields.Datetime.now(),
                            }
                        )
                        return {
                            "type": "ir.actions.client",
                            "tag": "display_notification",
                            "params": {
                                "title": _("Template Reset"),
                                "message": _("Template restored from filesystem."),
                                "sticky": False,
                                "next": {"type": "ir.actions.client", "tag": "reload"},
                            },
                        }
        return False

    def _notify_import(self, count, title=None):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title or _("Import Finished"),
                "message": _("Processed %s templates.") % count,
                "sticky": False,
            },
        }

    def action_export_txt(self):
        """Export the current filesystem TXT file as a download."""
        self.ensure_one()
        import base64

        base_path = self._get_base_path()
        templates_map = {
            "mipyme": "contrato marco Mipyme",
            "tcp": "contrato marco TCP.txt",
            "empresa": "contrato marco empresas.txt",
        }
        filename = templates_map.get(self.type)
        if not filename:
            raise UserError(_("Unknown template type."))

        template_path = os.path.join(base_path, filename)
        if not os.path.exists(template_path):
            raise UserError(
                _("The template file was not found on the filesystem: %s")
                % template_path
            )

        with open(template_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # Create a temporary attachment for download
        export_filename = filename if filename.endswith(".txt") else f"{filename}.txt"
        attachment = self.env["ir.attachment"].create(
            {
                "name": export_filename,
                "type": "binary",
                "datas": base64.b64encode(raw_content.encode("utf-8")),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "text/plain",
            }
        )

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def action_open_import_wizard(self):
        """Open the import TXT wizard for this template."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Import TXT"),
            "res_model": "contrato.template.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_template_id": self.id},
        }
