from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    disable_signatures = fields.Boolean(
        string="Deshabilitar firmas",
        default=False,
    )
