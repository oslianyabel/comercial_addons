from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    disable_signatures = fields.Boolean(
        related="company_id.disable_signatures",
        readonly=False,
        string="Deshabilitar firmas",
    )
    mi_empresa_partner_id = fields.Many2one(
        "res.partner",
        string="Mi Empresa",
        domain="[('is_company', '=', True)]",
        help="Contacto de tipo empresa que representa a tu organización.",
    )

    def get_values(self) -> dict:
        res = super().get_values()
        res["mi_empresa_partner_id"] = self.env.company.mi_empresa_partner_id.id
        return res

    def set_values(self) -> None:
        super().set_values()
        self.env.company.mi_empresa_partner_id = self.mi_empresa_partner_id
