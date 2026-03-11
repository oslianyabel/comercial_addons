from odoo import api, fields, models


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


class SignatureSettings(models.Model):
    _name = "signature.settings"
    _description = "Configuración de Firmas"

    signatures_disabled = fields.Boolean(
        string="Deshabilitar Firmas Digitales",
        default=False,
        help="Si se marca, las firmas digitales no serán requeridas para pasar a 'Firmado'.",
    )

    @api.model
    def get_settings(self):
        """Retrieve or create the singleton settings record."""
        return self.search([], limit=1) or self.create({})
