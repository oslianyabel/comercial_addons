from odoo import fields, models


class ContratosEmpresa(models.Model):
    _name = "contratos.empresa"
    _description = "Empresa"
    _order = "name"

    company_id = fields.Many2one(
        "res.partner",
        string="Compañía",
        domain=[("is_company", "=", True)],
        required=True,
        ondelete="restrict",
    )
    name = fields.Char(
        string="Nombre",
        related="company_id.name",
        store=True,
        readonly=False,
    )
    nit = fields.Char(string="NIT")
    unidad = fields.Char(string="Unidad")
    organismo_id = fields.Many2one(
        "res.partner.organism",
        string="Organismo",
    )
