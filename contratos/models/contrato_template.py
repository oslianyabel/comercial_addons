import os
import re

from odoo import _, fields, models
from odoo.exceptions import UserError


class ContratoTemplate(models.Model):
    _name = "contrato.template"
    _description = "Contract Template"
    _order = "sequence, id"

    name = fields.Char(string="Name", required=True)
    type = fields.Selection(
        [("mipyme", "MiPyme"), ("tcp", "TCP"), ("empresa", "Company")],
        string="Contract Type",
        required=True,
    )
    content = fields.Html(string="Template Content", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)

    _sql_constraints = [
        (
            "type_unique",
            "UNIQUE(type)",
            "A template for this contract type already exists.",
        )
    ]

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

    @models.api.model
    def _format_to_html(self, raw_content):
        """Standardized logic to convert plain text contract to Odoo-friendly HTML."""
        if not raw_content:
            return ""

        # Stricter detection of complex HTML.
        # If it's just raw text or basic spans from replacements, we want to format it.
        # We skip only if it has block structural elements like DIV, P, TABLE, etc.
        has_block_tags = re.search(
            r"<(p|div|h1|h2|h3|table|br|ul|ol|li)", raw_content, re.IGNORECASE
        )

        if has_block_tags:
            # If it's already HTML, just ensure double newlines become real spacing
            # Odoo's HTML editor sometimes inserts \n between tags.
            return raw_content.replace(
                "\n\n",
                '</p><p style="margin-bottom: 20px;">&nbsp;</p><p style="margin-bottom: 20px; text-align: justify; line-height: 1.6;">',
            )

        # Use splitlines() to handle \r\n (Windows), \n (Unix), etc.
        lineas = raw_content.splitlines()
        formatted_lineas = []
        for idx, linea in enumerate(lineas):
            linea = linea.strip()
            if not linea:
                # Force a physical vertical gap that Odoo won't collapse
                formatted_lineas.append(
                    '<p style="margin-bottom: 20px; line-height: 1.6;">&nbsp;</p>'
                )
                continue

            # Header detection (simplified but effective)
            is_header = len(linea) < 120 and (
                linea.isupper() or "CLÁUSULA" in linea.upper() or idx == 0
            )

            if is_header:
                font_size = "18px" if idx == 0 else "16px"
                formatted_lineas.append(
                    f'<h2 style="text-align: center; font-weight: bold; font-size: {font_size}; margin-top: 30px; margin-bottom: 15px;">{linea}</h2>'
                )
            else:
                # Standard paragraph with generous 20px bottom margin
                formatted_lineas.append(
                    f'<p style="text-align: justify; margin-bottom: 20px; line-height: 1.6;">{linea}</p>'
                )
        return "".join(formatted_lineas)

    def action_import_from_filesystem(self):
        """Utility to force import all templates from the known filesystem path."""
        base_path = "c:\\Users\\lilia\\Desktop\\Projects\\Odoo\\instancias\\odoo17_comercial2\\extra_addons\\context\\"
        templates = {
            "mipyme": "contrato marco Mipyme",
            "tcp": "contrato marco TCP.txt",
            "empresa": "contrato marco empresas.txt",
        }

        count = 0
        for c_type, filename in templates.items():
            template_path = os.path.join(base_path, filename)
            if os.path.exists(template_path):
                existing = self.search([("type", "=", c_type)], limit=1)
                if not existing:
                    with open(template_path, "r", encoding="utf-8") as f:
                        raw_content = f.read()
                        if raw_content:
                            self.create(
                                {
                                    "name": filename.replace(".txt", "").capitalize(),
                                    "type": c_type,
                                    "content": self._format_to_html(raw_content),
                                }
                            )
                            count += 1
        return self._notify_import(count)

    def action_reset_from_filesystem(self):
        """Force overwrite this template with the content from the filesystem."""
        base_path = "c:\\Users\\lilia\\Desktop\\Projects\\Odoo\\instancias\\odoo17_comercial2\\extra_addons\\context\\"
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
                        self.write({"content": self._format_to_html(raw_content)})
                        return self._notify_import(1, title=_("Template Reset"))
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
