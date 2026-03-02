from odoo import fields, models


class ResSignature(models.Model):
    _name = "signature.signature"
    _description = "Firma Digital"

    name = fields.Char(string="Nombre", required=True)
    image = fields.Binary(string="Imagen de Firma", required=True)

    partner_ids = fields.One2many(
        "res.partner", "signature_id", string="Contactos Asociados"
    )

    marco_ids = fields.Many2many(
        "contrato.marco",
        compute="_compute_marco_ids",
        string="Contratos Marcos Asociados",
    )

    def _compute_marco_ids(self):
        for record in self:
            records = self.env["contrato.marco"].search(
                [
                    "|",
                    ("provider_signature_id", "=", record.id),
                    ("customer_signature_id", "=", record.id),
                ]
            )
            record.marco_ids = records
