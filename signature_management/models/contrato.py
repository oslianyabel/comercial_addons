import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ContratoMarco(models.Model):
    _inherit = "contrato.marco"

    provider_signature_id = fields.Many2one(
        "signature.signature", string="Firma del Prestador"
    )
    customer_signature_id = fields.Many2one(
        "signature.signature", string="Firma del Cliente"
    )

    signatures_disabled = fields.Boolean(
        compute="_compute_signatures_disabled", string="Firmas Deshabilitadas"
    )

    def _compute_signatures_disabled(self):
        for record in self:
            record.signatures_disabled = self.env.company.disable_signatures

    def action_draft(self):
        """Revert to draft state. Allowed from 'cancelado'."""
        for record in self:
            if record.state != "cancelado":
                raise UserError(_("Only cancelled contracts can be set back to draft."))
        return super().action_draft()

    def action_cancel(self):
        """Cancel the contract. Allowed from 'borrador', 'entregado', or 'firmado'."""
        for record in self:
            if record.state not in ["borrador", "entregado", "firmado"]:
                raise UserError(
                    _("Only draft, delivered, or signed contracts can be cancelled.")
                )
        return super().action_cancel()

    def action_sign(self):
        """Transition contract to delivered state. Requires both signatures."""
        for record in self:
            if record.state != "borrador":
                raise UserError(_("Only draft contracts can be signed."))
            if not record.signatures_disabled and (
                not record.provider_signature_id or not record.customer_signature_id
            ):
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


class ContratoEspecificoLine(models.Model):
    _inherit = "contrato.especifico.line"

    invoice_id = fields.Many2one(
        "account.move",
        string="Factura",
        compute="_compute_invoice_data",
        store=True,
    )
    invoice_state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("posted", "Publicada"),
            ("cancel", "Cancelada"),
        ],
        string="Estado de Factura",
        compute="_compute_invoice_data",
        store=True,
    )
    is_atrasada = fields.Boolean(
        string="Facturada con Retraso",
        compute="_compute_is_atrasada",
        store=True,
    )

    @api.depends("invoiced")
    def _compute_invoice_data(self):
        super()._compute_invoice_data()

    @api.depends("invoice_id.invoice_date", "date_deadline_invoice")
    def _compute_is_atrasada(self):
        for line in self:
            inv_date = line.invoice_id.invoice_date if line.invoice_id else False
            deadline = line.date_deadline_invoice
            line.is_atrasada = bool(inv_date and deadline and inv_date > deadline)

    def action_open_invoice(self) -> dict:
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_contrato(self) -> dict:
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "contrato.especifico",
            "res_id": self.contrato_id.id,
            "view_mode": "form",
            "target": "current",
        }

    contrato_state = fields.Selection(
        [
            ("borrador", "Draft"),
            ("entregado", "Entregado"),
            ("firmado", "Signed"),
            ("cancelado", "Cancelled"),
        ],
        string="Estado del Contrato",
        related="contrato_id.state",
        store=True,
    )

    is_deadline_past = fields.Boolean(
        string="Plazo Vencido",
        compute="_compute_deadline_status",
    )
    is_deadline_soon = fields.Boolean(
        string="Plazo Próximo",
        compute="_compute_deadline_status",
    )

    @api.depends("date_deadline_invoice")
    def _compute_deadline_status(self):
        today = fields.Date.today()
        soon_limit = today + timedelta(days=7)
        for line in self:
            deadline = line.date_deadline_invoice
            if deadline:
                line.is_deadline_past = deadline < today
                line.is_deadline_soon = (
                    not line.is_deadline_past and deadline <= soon_limit
                )
            else:
                line.is_deadline_past = False
                line.is_deadline_soon = False

    notif_vencida_sent = fields.Boolean(
        string="Notificación Vencida Enviada",
        default=False,
        copy=False,
    )
    notif_proxima_sent = fields.Boolean(
        string="Notificación Próxima Enviada",
        default=False,
        copy=False,
    )

    def write(self, vals: dict) -> bool:
        if "date_deadline_invoice" in vals:
            vals["notif_vencida_sent"] = False
            vals["notif_proxima_sent"] = False
        return super().write(vals)

    @api.model
    def _cron_check_billing_deadlines(self) -> None:
        """Sends push notifications for uninvoiced lines that are overdue or
        due within 3 days. Each notification is sent only once per line."""
        from odoo.addons.telegram_notifier.telegram_service import send_message

        today = fields.Date.today()
        soon_threshold = today + timedelta(days=3)

        base_domain = [("invoiced", "=", False), ("is_invoice_line", "=", False)]

        overdue_lines = self.search(
            base_domain
            + [
                ("date_deadline_invoice", "<", today),
                ("notif_vencida_sent", "=", False),
            ]
        )
        upcoming_lines = self.search(
            base_domain
            + [
                ("date_deadline_invoice", ">=", today),
                ("date_deadline_invoice", "<=", soon_threshold),
                ("notif_proxima_sent", "=", False),
            ]
        )

        internal_partners = (
            self.env["res.users"]
            .search([("share", "=", False), ("active", "=", True)])
            .mapped("partner_id")
        )

        if overdue_lines:
            count = len(overdue_lines)
            bus_msg = {
                "title": "⚠️ Líneas de servicio vencidas",
                "message": (
                    f"Hay {count} línea(s) de servicio con Límite de Facturación "
                    "vencido que aún no se han facturado."
                ),
                "type": "warning",
                "sticky": True,
            }
            for partner in internal_partners:
                self.env["bus.bus"]._sendone(partner, "simple_notification", bus_msg)

            lines_detail = "\n".join(
                f"  • {l.contrato_id.name} | {l.name} | Límite: {l.date_deadline_invoice}"
                for l in overdue_lines
            )
            send_message(
                f"⚠️ Líneas de servicio VENCIDAS sin facturar: {count}\n\n{lines_detail}"
            )
            overdue_lines.with_context(is_uninvoice=True).write(
                {"notif_vencida_sent": True}
            )
            _logger.info(
                "Billing deadline cron: sent overdue notification for %d lines.", count
            )

        if upcoming_lines:
            count = len(upcoming_lines)
            bus_msg = {
                "title": "🔔 Líneas de servicio próximas a vencer",
                "message": (
                    f"Hay {count} línea(s) de servicio con Límite de Facturación "
                    "en los próximos 3 días que aún no se han facturado."
                ),
                "type": "warning",
                "sticky": True,
            }
            for partner in internal_partners:
                self.env["bus.bus"]._sendone(partner, "simple_notification", bus_msg)

            lines_detail = "\n".join(
                f"  • {l.contrato_id.name} | {l.name} | Límite: {l.date_deadline_invoice}"
                for l in upcoming_lines
            )
            send_message(
                f"🔔 Líneas de servicio próximas a vencer ({count}):\n\n{lines_detail}"
            )
            upcoming_lines.with_context(is_uninvoice=True).write(
                {"notif_proxima_sent": True}
            )
            _logger.info(
                "Billing deadline cron: sent upcoming notification for %d lines.", count
            )

    def action_facturar_multiples_wizard(self) -> dict:
        """Abre el wizard de facturación para las líneas uninvoiced seleccionadas."""
        lines = self.filtered(lambda l: not l.invoiced and not l.is_invoice_line)
        if not lines:
            raise UserError(
                _("No hay líneas pendientes de facturar entre las seleccionadas.")
            )
        contracts = lines.mapped("contrato_id")
        if len(contracts) > 1:
            raise UserError(
                _(
                    "Solo puede facturar líneas de un único contrato en una operación. "
                    "Seleccione líneas pertenecientes al mismo contrato."
                )
            )
        wizard = self.env["lineas.por.facturar.multiples.wizard"].create(
            {
                "line_ids": [(6, 0, lines.ids)],
                "contrato_id": contracts.id,
            }
        )
        return {
            "name": _("Facturar Líneas Seleccionadas"),
            "type": "ir.actions.act_window",
            "res_model": "lineas.por.facturar.multiples.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }


class ContratoEspecifico(models.Model):
    _inherit = "contrato.especifico"

    provider_signature_id = fields.Many2one(
        "signature.signature", string="Firma del Prestador"
    )
    customer_signature_id = fields.Many2one(
        "signature.signature", string="Firma del Cliente"
    )

    signatures_disabled = fields.Boolean(
        compute="_compute_signatures_disabled", string="Firmas Deshabilitadas"
    )

    def _compute_signatures_disabled(self):
        for record in self:
            record.signatures_disabled = self.env.company.disable_signatures

    # Audit fields - REMOVED as per user request
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
        if self.env.context.get("from_master_cancel"):
            return
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
            if record.state not in ["borrador", "entregado", "firmado"]:
                raise UserError(
                    _("Only draft, delivered, or signed contracts can be cancelled.")
                )
        return super().action_cancel()

    def action_sign(self):
        """Check permissions, flow, and signatures for signing."""
        self._check_state_change_permission()
        for record in self:
            if record.state != "borrador":
                raise UserError(_("Only draft contracts can be signed."))
            if not record.signatures_disabled and (
                not record.provider_signature_id or not record.customer_signature_id
            ):
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

    def _report_check_state(self):
        """Helper method to check state during report rendering."""
        self.ensure_one()
        if self.state != "firmado":
            raise UserError(
                _(
                    "No se puede imprimir el contrato '%s' porque no está en estado Firmado."
                )
                % self.name
            )
        return ""

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
