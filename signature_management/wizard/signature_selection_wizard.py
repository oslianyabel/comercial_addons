from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SignatureSelectionWizard(models.TransientModel):
    _name = "signature.selection.wizard"
    _description = "Signature Selection for Invoicing"

    line_id = fields.Many2one(
        "contrato.especifico.line", string="Service Line", required=True
    )
    contrato_id = fields.Many2one(
        "contrato.especifico", related="line_id.contrato_id", string="Contract"
    )

    payment_form_id = fields.Many2one(
        "signature.payment.form", string="Forma de pago", required=True
    )

    # Roles: Contact + Date
    realizada_por_id = fields.Many2one("res.partner", string="Realizada por")
    realizada_fecha = fields.Date(string="Fecha (Realizada)", default=fields.Date.today)

    transportado_por_id = fields.Many2one("res.partner", string="Transportado por")
    transportado_fecha = fields.Date(
        string="Fecha (Transportado)", default=fields.Date.today
    )

    recibido_por_id = fields.Many2one("res.partner", string="Recibido por")
    recibido_fecha = fields.Date(string="Fecha (Recibido)", default=fields.Date.today)

    entregada_por_id = fields.Many2one("res.partner", string="Entregada por")
    entregada_fecha = fields.Date(string="Fecha (Entregada)", default=fields.Date.today)

    contabilizada_por_id = fields.Many2one("res.partner", string="Contabilizada por")
    contabilizada_fecha = fields.Date(
        string="Fecha (Contabilizada)", default=fields.Date.today
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get(
            "active_model"
        ) == "contrato.especifico.line" and self._context.get("active_id"):
            line = self.env["contrato.especifico.line"].browse(
                self._context.get("active_id")
            )
            res["line_id"] = line.id
        return res

    def action_confirm(self):
        self.ensure_one()
        if self.line_id.invoiced:
            raise UserError(_("This line is already invoiced."))

        contract = self.line_id.contrato_id

        # 1. Validation: Contract must be Signed
        if contract.state != "firmado":
            raise UserError(
                _("You can only invoice service lines for a Signed contract.")
            )

        # 2. Validation: All selected contacts must have a signature assigned
        roles = [
            ("Realizada por", self.realizada_por_id),
            ("Transportado por", self.transportado_por_id),
            ("Recibido por", self.recibido_por_id),
            ("Entregada por", self.entregada_por_id),
            ("Contabilizada por", self.contabilizada_por_id),
        ]
        missing_signatures = []
        for role_label, partner in roles:
            if partner and not partner.signature_id:
                missing_signatures.append(f"{role_label}: {partner.name}")

        if missing_signatures:
            raise UserError(
                _(
                    "The following contacts do not have a signature record assigned:\n\n%s\n\n"
                    "Please go to the contact form and assign a signature before invoicing."
                )
                % "\n".join(f"- {m}" for m in missing_signatures)
            )

        partner = contract.partner_id

        # Mapping for account.move
        invoice_vals = {
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_date": fields.Date.today(),
            "contrato_especifico_id": contract.id,
            "service_line_id": self.line_id.id,
            "payment_form_id": self.payment_form_id.id,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.line_id.product_id.id,
                        "name": self.line_id.name,
                        "quantity": self.line_id.quantity,
                        "product_uom_id": self.line_id.uom_id.id,
                        "price_unit": self.line_id.price_unit,
                    },
                )
            ],
            "client_address": f"{partner.street or ''} {partner.city or ''}".strip(),
            "client_nit": partner.vat or partner.tax_id or "",
            "client_bank_account": partner.bank_account_cup or "",
            # Role mapping
            "realizada_por_id": self.realizada_por_id.id,
            "realizada_fecha": self.realizada_fecha,
            "transportado_por_id": self.transportado_por_id.id,
            "transportado_fecha": self.transportado_fecha,
            "recibido_por_id": self.recibido_por_id.id,
            "recibido_fecha": self.recibido_fecha,
            "entregada_por_id": self.entregada_por_id.id,
            "entregada_fecha": self.entregada_fecha,
            "contabilizada_por_id": self.contabilizada_por_id.id,
            "contabilizada_fecha": self.contabilizada_fecha,
        }

        move = self.env["account.move"].create(invoice_vals)
        # We allow this update even if contract is signed because we modified _check_signed_contract
        self.line_id.with_context(is_uninvoice=True).write({"invoiced": True})

        return {
            "name": _("Invoice"),
            "view_mode": "form",
            "res_model": "account.move",
            "res_id": move.id,
            "type": "ir.actions.act_window",
        }
