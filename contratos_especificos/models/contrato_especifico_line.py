from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContratoEspecificoLine(models.Model):
    _name = "contrato.especifico.line"
    _description = "Specific Contract Service Line"

    contrato_id = fields.Many2one(
        "contrato.especifico",
        string="Specific Contract",
        ondelete="cascade",
        required=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Service/Product",
        required=True,
    )
    name = fields.Char(string="Description", required=True)
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        required=True,
    )
    price_unit = fields.Float(string="Unit Price (CUP)", required=True)
    price_subtotal = fields.Float(
        string="Subtotal",
        compute="_compute_price_subtotal",
        store=True,
    )
    date_deadline_invoice = fields.Date(
        string="Invoice Deadline Date",
        required=True,
    )
    invoiced = fields.Boolean(
        string="Invoiced",
        default=False,
        readonly=True,
    )

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id.id
            self.price_unit = self.product_id.lst_price

    def _check_signed_contract(self, vals=None):
        """Block modifications on signed contracts, unless only updating administrative fields like 'invoiced'."""
        if self._context.get("is_uninvoice"):
            return

        administrative_fields = {"invoiced"}

        # If vals is provided, check if we are ONLY updating administrative fields
        if vals and all(field in administrative_fields for field in vals.keys()):
            return

        for line in self:
            if line.contrato_id and line.contrato_id.state == "firmado":
                raise UserError(
                    _(
                        "You cannot modify, create or delete service lines for a contract that is already signed."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("contrato_id"):
                contract = self.env["contrato.especifico"].browse(vals["contrato_id"])
                if contract.state == "firmado":
                    raise UserError(
                        _("You cannot add lines to a contract that is already signed.")
                    )
        return super().create(vals_list)

    def write(self, vals):
        self._check_signed_contract(vals)
        return super().write(vals)

    def unlink(self):
        self._check_signed_contract()
        return super().unlink()

    def action_uninvoice(self):
        """Reset the invoiced flag and delete associated invoices."""
        for line in self:
            if not line.invoiced:
                continue
            # Find and delete associated invoices
            invoices = self.env["account.move"].search(
                [("service_line_id", "=", line.id)]
            )
            # Only allow deleting draft or cancelled invoices for safety,
            # but user requested it should delete it.
            # In Odoo, deleting posted invoices usually requires resetting to draft first.
            for inv in invoices:
                if inv.state == "posted":
                    inv.button_draft()
                inv.unlink()

            # Bypass the manual write check by using super().write or context
            line.with_context(is_uninvoice=True).write({"invoiced": False})
