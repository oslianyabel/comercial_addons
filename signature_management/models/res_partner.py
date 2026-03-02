from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Invoicing Metadata moved to signature_management for correct dependency handling
    ch_number = fields.Char(string="CH")
    license_number = fields.Char(string="License")
    signature_id = fields.Many2one("signature.signature", string="Signature")
