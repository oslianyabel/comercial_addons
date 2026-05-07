from odoo import api, fields, models


class ContratoEspecificoSupplementoLine(models.Model):
    _name = "contrato.especifico.suplemento.line"
    _description = "Línea de Servicio de Suplemento de Contrato Específico"

    suplemento_id = fields.Many2one(
        "contrato.especifico.suplemento",
        string="Suplemento",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto/Servicio",
        required=True,
    )
    name = fields.Char(string="Descripción", required=True)
    quantity = fields.Float(string="Cantidad", default=1.0, required=True)
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unidad de Medida",
        required=True,
    )
    price_unit = fields.Float(string="Precio Unitario (CUP)", required=True)
    price_subtotal = fields.Float(
        string="Subtotal",
        compute="_compute_price_subtotal",
        store=True,
    )
    date_deadline_invoice = fields.Date(string="Fecha Límite de Facturación")
    start_date = fields.Date(string="Fecha de Inicio")
    end_date = fields.Date(string="Fecha Final")

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self) -> None:
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
