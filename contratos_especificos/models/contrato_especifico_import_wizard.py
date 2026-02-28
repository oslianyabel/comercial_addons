import base64
import os

from odoo import _, fields, models
from odoo.exceptions import UserError


class ContratoEspecificoImportWizard(models.TransientModel):
    _name = "contrato.especifico.import.wizard"
    _description = "Import TXT for Specific Contract Template"

    template_id = fields.Many2one(
        "contrato.especifico.template",
        string="Template",
        required=True,
    )
    file_data = fields.Binary(string="TXT File", required=True)
    file_name = fields.Char(string="File Name")

    def action_import(self):
        self.ensure_one()

        if not self.file_data:
            raise UserError(_("Please select a TXT file to import."))

        try:
            raw_content = base64.b64decode(self.file_data).decode("utf-8")
        except UnicodeDecodeError:
            raise UserError(
                _(
                    "The file could not be read. Please ensure it is a valid UTF-8 text file."
                )
            )

        if not raw_content.strip():
            raise UserError(_("The uploaded file is empty."))

        template = self.template_id
        template._validate_content_variables(raw_content, template.type)

        base_path = template._get_base_path()
        filename = template.TEMPLATE_FILES.get(template.type)
        if not filename:
            raise UserError(_("Unknown template type."))

        template_path = os.path.join(base_path, filename)

        os.makedirs(base_path, exist_ok=True)
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(raw_content)

        template.action_reset_from_filesystem()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import Successful"),
                "message": _(
                    "The template file has been replaced and the template content has been updated."
                ),
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
