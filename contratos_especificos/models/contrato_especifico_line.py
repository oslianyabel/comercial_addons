from odoo import api, fields, models


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
