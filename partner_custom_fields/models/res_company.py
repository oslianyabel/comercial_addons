from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    organism_id = fields.Many2one("res.partner.organism", string="Organism")
    contract_name = fields.Char(
        string="Company Name in Contracts",
        default="5100436311 Soluciones Dteam SURL IRCC",
    )
    unit = fields.Char(string="Unit", default="28 SOLUCIONES DTEAM S.U.R.L")
    address_legal = fields.Char(string="Legal Address", default="Maximo gomez 179")
    nit_code = fields.Char(string="NIT Code", default="51004363111")
    stamp_image = fields.Binary(string="Company Stamp")
