from odoo import _, models
from odoo.exceptions import UserError


class ContratoMarco(models.Model):
    _inherit = "contrato.marco"

    def action_set_to_pending(self):
        """Restrict reverting to pending if specific contracts exist."""
        for record in self:
            if record.state == "firmado":
                specific_contracts = self.env["contrato.especifico"].search_count(
                    [("marco_id", "=", record.id)]
                )
                if specific_contracts > 0:
                    raise UserError(
                        _(
                            "You cannot set this master contract to 'Pending' because it has %s associated specific contracts."
                        )
                        % specific_contracts
                    )
        return super().action_set_to_pending()
