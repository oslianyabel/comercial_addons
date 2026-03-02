from odoo import fields, models


class ResSignature(models.Model):
    _name = "signature.signature"
    _description = "Digital Signature"

    name = fields.Char(string="Name", required=True)
    image = fields.Binary(string="Signature Image", required=True)
    job_title = fields.Char(string="Cargo")
    id_card = fields.Char(string="CI")
    license_number = fields.Char(string="Lic")
    ch_number = fields.Char(string="CH")

    partner_ids = fields.One2many(
        "res.partner", "signature_id", string="Associated Contacts"
    )

    marco_ids = fields.Many2many(
        "contrato.marco",
        compute="_compute_marco_ids",
        string="Associated Master Contracts",
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
