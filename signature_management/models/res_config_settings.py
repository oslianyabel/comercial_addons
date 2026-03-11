from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    disable_signatures = fields.Boolean(
        related="company_id.disable_signatures",
        readonly=False,
        string="Deshabilitar firmas",
    )
