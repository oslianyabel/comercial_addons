from odoo import fields, models


class ResSignature(models.Model):
    _name = "signature.signature"
    _description = "Digital Signature"

    name = fields.Char(string="Name", required=True)
    image = fields.Binary(string="Signature Image", required=True)
