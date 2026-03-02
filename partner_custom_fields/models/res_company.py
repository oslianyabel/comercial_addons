from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    organism_id = fields.Many2one("res.partner.organism", string="Organismo")
    contract_name = fields.Char(
        string="Nombre de la Empresa en Contratos",
        default="5100436311 Soluciones Dteam SURL IRCC",
    )
    unit = fields.Char(string="Unidad", default="28 SOLUCIONES DTEAM S.U.R.L")
    address_legal = fields.Char(string="Dirección Legal", default="Maximo gomez 179")
    nit_code = fields.Char(string="Código NIT", default="51004363111")
    stamp_image = fields.Binary(string="Sello de la Empresa")
