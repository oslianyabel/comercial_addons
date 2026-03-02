from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContratoMarco(models.Model):
    _inherit = "contrato.marco"

    provider_signature_id = fields.Many2one(
        "signature.signature", string="Firma del Prestador"
    )
    customer_signature_id = fields.Many2one(
        "signature.signature", string="Firma del Cliente"
    )

    def action_draft(self):
        """Revert to draft state. Allowed from 'cancelado'."""
        for record in self:
            if record.state != "cancelado":
                raise UserError(_("Only cancelled contracts can be set back to draft."))
        return super().action_draft()

    def action_cancel(self):
        """Cancel the contract. Allowed from 'borrador' or 'firmado'."""
        for record in self:
            if record.state not in ["borrador", "firmado"]:
                raise UserError(_("Only draft or signed contracts can be cancelled."))
        return super().action_cancel()

    def action_sign(self):
        """Transition contract to signed state. Requires both signatures."""
        for record in self:
            if record.state != "borrador":
                raise UserError(_("Only draft contracts can be signed."))
            if not record.provider_signature_id or not record.customer_signature_id:
                raise UserError(
                    _(
                        "Both Provider and Customer signatures must be set before signing."
                    )
                )
        return super().action_sign()

    def unlink(self):
        """Block deletion if specific contracts exist."""
        for record in self:
            specific_contracts = self.env["contrato.especifico"].search_count(
                [("marco_id", "=", record.id)]
            )
            if specific_contracts > 0:
                raise UserError(
                    _(
                        "You cannot delete this master contract because it has %s associated specific contracts. "
                        "Please delete them manually first."
                    )
                    % specific_contracts
                )
        return super().unlink()


class ContratoEspecifico(models.Model):
    _inherit = "contrato.especifico"

    provider_signature_id = fields.Many2one(
        "signature.signature", string="Firma del Prestador"
    )
    customer_signature_id = fields.Many2one(
        "signature.signature", string="Firma del Cliente"
    )

    # Audit fields
    realizada_por_id = fields.Many2one("signature.signature", string="Realizada por")
    transportado_por_id = fields.Many2one(
        "signature.signature", string="Transportado por"
    )
    recibido_por_id = fields.Many2one("signature.signature", string="Recibido por")
    entregada_por_id = fields.Many2one("signature.signature", string="Entregada por")
    contabilizada_por_id = fields.Many2one(
        "signature.signature", string="Contabilizada por"
    )

    invoice_count = fields.Integer(compute="_compute_invoice_count")

    service_line_state = fields.Selection(
        [
            ("pending", "Facturas pendientes"),
            ("delayed", "Facturas atrasadas"),
            ("invoiced", "Facturado"),
        ],
        string="Estado de facturación de servicios",
        compute="_compute_service_line_state",
        store=True,
    )

    @api.depends("line_ids.invoiced", "line_ids.date_deadline_invoice")
    def _compute_service_line_state(self):
        today = fields.Date.today()
        for record in self:
            if not record.line_ids:
                record.service_line_state = "pending"
                continue

            all_invoiced = all(line.invoiced for line in record.line_ids)
            if all_invoiced:
                record.service_line_state = "invoiced"
            else:
                # Check for delays in uninvoiced lines
                uninvoiced_lines = record.line_ids.filtered(
                    lambda line: not line.invoiced
                )
                # Check deadline
                has_delay = False
                for line in uninvoiced_lines:
                    if (
                        line.date_deadline_invoice
                        and line.date_deadline_invoice < today
                    ):
                        has_delay = True
                        break

                if has_delay:
                    record.service_line_state = "delayed"
                else:
                    record.service_line_state = "pending"

    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = self.env["account.move"].search_count(
                [("contrato_especifico_id", "=", record.id)]
            )

    def _check_state_change_permission(self):
        """Verify if the current user is an authorized contact in the Master Contract."""
        for record in self:
            user_partner = self.env.user.partner_id
            if (
                user_partner not in record.marco_id.authorized_contact_ids
                and not self.env.is_admin()
            ):
                raise UserError(
                    _(
                        "Only authorized contacts from the Master Contract (%s) can change the state of this Specific Contract."
                    )
                    % record.marco_id.name
                )

    def action_draft(self):
        """Revert to draft state, but block if invoiced lines exist and check permissions."""
        self._check_state_change_permission()
        for record in self:
            if record.state != "cancelado":
                raise UserError(_("Only cancelled contracts can be set back to draft."))
            if any(line.invoiced for line in record.line_ids):
                raise UserError(
                    _(
                        "You cannot set the contract to draft because there are invoiced service lines. "
                        "Please uninvoice the lines first."
                    )
                )
        return super().action_draft()

    def action_cancel(self):
        """Check permissions and flow for cancellation."""
        self._check_state_change_permission()
        for record in self:
            if record.state not in ["borrador", "firmado"]:
                raise UserError(_("Only draft or signed contracts can be cancelled."))
        return super().action_cancel()

    def action_sign(self):
        """Check permissions, flow, and signatures for signing."""
        self._check_state_change_permission()
        for record in self:
            if record.state != "borrador":
                raise UserError(_("Only draft contracts can be signed."))
            if not record.provider_signature_id or not record.customer_signature_id:
                raise UserError(
                    _(
                        "Both Provider and Customer signatures must be set before signing."
                    )
                )
        return super().action_sign()

    def unlink(self):
        """Standard unlink override to perform cascading deletion of invoices."""
        for record in self:
            invoices = self.env["account.move"].search(
                [("contrato_especifico_id", "=", record.id)]
            )
            if invoices:
                # Reset to draft if posted, then unlink
                for inv in invoices:
                    if inv.state == "posted":
                        inv.button_draft()
                invoices.unlink()
        return super().unlink()

    def action_view_invoices(self):
        self.ensure_one()
        # Find the restricted view
        view_reference = "signature_management.view_move_tree_contract_restricted"
        view_id = self.env.ref(view_reference).id
        return {
            "name": _("Invoices"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "tree,form",
            "views": [(view_id, "tree"), (False, "form")],
            "domain": [("contrato_especifico_id", "=", self.id)],
            "context": {
                "default_contrato_especifico_id": self.id,
                "create": False,
                "delete": True,
                "import": False,
                "import_any_file": False,
            },
        }
