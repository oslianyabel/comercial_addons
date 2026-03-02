from odoo import _, api, fields, models


class ContratoEspecificoDeleteWizard(models.TransientModel):
    _name = "contrato.especifico.delete.wizard"
    _description = "Specific Contract Deletion Warning"

    contrato_id = fields.Many2one(
        "contrato.especifico", string="Contract", required=True
    )
    invoice_ids = fields.Many2many(
        "account.move",
        string="Associated Invoices to Delete",
        compute="_compute_invoices",
    )
    invoice_count = fields.Integer(compute="_compute_invoices")

    @api.depends("contrato_id")
    def _compute_invoices(self):
        for record in self:
            invoices = self.env["account.move"].search(
                [("contrato_especifico_id", "=", record.contrato_id.id)]
            )
            record.invoice_ids = invoices
            record.invoice_count = len(invoices)

    def action_confirm_delete(self):
        self.ensure_one()
        contract = self.contrato_id
        invoices = self.invoice_ids

        # Delete invoices first
        if invoices:
            # Reset to draft if posted, then unlink
            for inv in invoices:
                if inv.state == "posted":
                    inv.button_draft()
            invoices.unlink()

        # Delete the contract
        contract.unlink()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Contract and associated invoices have been deleted."),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }
