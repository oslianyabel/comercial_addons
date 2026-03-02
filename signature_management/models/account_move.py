from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    contrato_especifico_id = fields.Many2one(
        "contrato.especifico", string="Specific Contract"
    )
    service_line_id = fields.Many2one("contrato.especifico.line", string="Service Line")
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

    def unlink(self):
        """Reset the 'invoiced' flag on the related service line when the invoice is deleted."""
        # Collect service lines and contracts before deletion
        service_lines = self.mapped("service_line_id")
        contracts = service_lines.mapped("contrato_id")

        res = super().unlink()

        if service_lines:
            # Use sudo() to bypass potential permission issues during bulk deletion
            service_lines.sudo().with_context(is_uninvoice=True).write(
                {"invoiced": False}
            )
            # Explicitly trigger recompute of the stored service_line_state on the contracts
            if contracts:
                contracts.sudo()._compute_service_line_state()
        return res
