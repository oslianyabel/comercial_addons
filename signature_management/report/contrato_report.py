from odoo import _, api, models
from odoo.exceptions import UserError


class ReportContratoEspecifico(models.AbstractModel):
    _name = "report.signature_management.report_contrato_especifico_template"
    _description = "Specific Contract Report Logic"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["contrato.especifico"].browse(docids)
        for doc in docs:
            if doc.state != "firmado":
                raise UserError(
                    _(
                        "No se puede imprimir el contrato '%s' porque no está en estado Firmado."
                    )
                    % doc.name
                )
        return {
            "doc_ids": docids,
            "doc_model": "contrato.especifico",
            "docs": docs,
            "data": data,
        }
