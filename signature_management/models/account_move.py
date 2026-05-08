from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    contrato_especifico_id = fields.Many2one(
        "contrato.especifico", string="Specific Contract"
    )
    service_line_id = fields.Many2one("contrato.especifico.line", string="Service Line")
    ueb_service_line_id = fields.Many2one(
        "contrato.especifico.ueb.line", string="UEB Service Line"
    )
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

    def write(self, vals):
        result = super().write(vals)
        if "invoice_line_ids" in vals:
            for move in self:
                move._sync_invoice_lines_to_service_lines()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for move in records:
            if move.contrato_especifico_id and move.move_type == "out_invoice":
                move._assign_contrato_invoice_name()
        return records

    def _assign_contrato_invoice_name(self) -> None:
        """Assign a custom name FACT_<consecutive>_<contract_number> to the invoice."""
        self.ensure_one()
        contract = self.contrato_especifico_id
        if not contract:
            return
        existing_count = self.env["account.move"].search_count(
            [
                ("contrato_especifico_id", "=", contract.id),
                ("id", "!=", self.id),
                ("move_type", "=", "out_invoice"),
            ]
        )
        consecutive = existing_count + 1
        self.with_context(no_resequence=True).write(
            {"name": f"FACT_{consecutive:02d}_{contract.name}"}
        )

    def action_open_contrato_especifico(self) -> dict:
        """Open the linked specific contract form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico",
            "res_id": self.contrato_especifico_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _sync_invoice_lines_to_service_lines(self) -> None:
        """Propagate quantity and price_unit changes from invoice product lines to the linked service line."""
        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        )
        if not product_lines:
            return
        inv_line = product_lines[0]

        for svc_line in filter(None, [self.service_line_id, self.ueb_service_line_id]):
            updates: dict = {}
            if svc_line.quantity != inv_line.quantity:
                updates["quantity"] = inv_line.quantity
            if svc_line.price_unit != inv_line.price_unit:
                updates["price_unit"] = inv_line.price_unit
            if updates:
                svc_line.with_context(is_uninvoice=True).write(updates)

    def unlink(self):
        """Reset the 'invoiced' flag on the related service line when the invoice is deleted."""
        # Collect service lines and contracts before deletion
        service_lines = self.mapped("service_line_id")
        ueb_service_lines = self.mapped("ueb_service_line_id")
        contracts = service_lines.mapped("contrato_id")

        res = super().unlink()

        if service_lines:
            service_lines.sudo().with_context(is_uninvoice=True).write(
                {"invoiced": False}
            )
            if contracts:
                contracts.sudo()._compute_service_line_state()

        if ueb_service_lines:
            ueb_service_lines.sudo().with_context(is_uninvoice=True).write(
                {"invoiced": False}
            )

        return res
