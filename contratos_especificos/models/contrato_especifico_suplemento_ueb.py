from odoo import api, fields, models


class ContratoEspecificoSupplementoUebSection(models.Model):
    _name = "contrato.especifico.suplemento.ueb.section"
    _description = "Sección UEB de Suplemento de Contrato Específico"
    _order = "sequence, id"

    suplemento_id = fields.Many2one(
        "contrato.especifico.suplemento",
        string="Suplemento",
        required=True,
        ondelete="cascade",
    )
    ueb_id = fields.Many2one(
        "res.partner.ueb",
        string="UEB",
        required=True,
    )
    sequence = fields.Integer(default=10)
    line_ids = fields.One2many(
        "contrato.especifico.suplemento.ueb.line",
        "section_id",
        string="Líneas de Servicio",
    )
    total_amount = fields.Float(
        string="Total",
        compute="_compute_total_amount",
    )

    @api.depends("line_ids.price_subtotal")
    def _compute_total_amount(self) -> None:
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped("price_subtotal"))


class ContratoEspecificoSupplementoUebLine(models.Model):
    _name = "contrato.especifico.suplemento.ueb.line"
    _description = "Línea de Servicio UEB de Suplemento de Contrato Específico"

    section_id = fields.Many2one(
        "contrato.especifico.suplemento.ueb.section",
        string="Sección UEB",
        required=True,
        ondelete="cascade",
    )
    suplemento_id = fields.Many2one(
        "contrato.especifico.suplemento",
        related="section_id.suplemento_id",
        store=True,
        string="Suplemento",
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
    original_invoiced = fields.Boolean(
        string="Fue Facturada",
        default=False,
        help="Indica que la línea original ya estaba facturada al crear este suplemento.",
    )

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self) -> None:
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
