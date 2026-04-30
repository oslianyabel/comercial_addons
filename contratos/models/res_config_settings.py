from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    master_contract_validity_years = fields.Integer(
        string="Tiempo de Validez por Defecto",
        config_parameter="contratos.master_contract_validity_years",
        default=5,
    )
    contratos_default_validity_years = fields.Integer(
        related="master_contract_validity_years",
        readonly=False,
    )
    specific_contract_validity_years = fields.Integer(
        string="Tiempo de Validez por Defecto (Contratos Específicos)",
        config_parameter="contratos.specific_contract_validity_years",
        default=1,
    )
