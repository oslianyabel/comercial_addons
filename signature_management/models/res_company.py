from odoo import _, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    disable_signatures = fields.Boolean(
        string="Deshabilitar firmas",
        default=False,
    )
    mi_empresa_partner_id = fields.Many2one(
        "res.partner",
        string="Mi Empresa",
        domain="[('is_company', '=', True)]",
        help="Contacto de tipo empresa que representa a tu organización en los contratos.",
    )

    def action_view_trabajadores(self) -> dict:
        """Open the list of contacts linked to Mi Empresa."""
        company = self.env.company
        if company.mi_empresa_partner_id:
            domain: list = [("parent_id", "=", company.mi_empresa_partner_id.id)]
        else:
            domain = [("is_company", "=", False), ("parent_id", "!=", False)]
        return {
            "type": "ir.actions.act_window",
            "name": _("Trabajadores"),
            "res_model": "res.partner",
            "view_mode": "tree,form",
            "domain": domain,
        }

    def action_view_clientes(self) -> dict:
        """Open the list of company contacts excluding Mi Empresa."""
        company = self.env.company
        domain: list = [("is_company", "=", True)]
        if company.mi_empresa_partner_id:
            domain.append(("id", "!=", company.mi_empresa_partner_id.id))
        return {
            "type": "ir.actions.act_window",
            "name": _("Clientes"),
            "res_model": "res.partner",
            "view_mode": "tree,form",
            "domain": domain,
        }
