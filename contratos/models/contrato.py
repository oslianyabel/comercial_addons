from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContratoMarco(models.Model):
    _name = "contrato.marco"
    _description = "Master Contract"

    name = fields.Char(string="Contract Number", required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        domain=[("is_company", "=", True)],
    )
    representative_id = fields.Many2one(
        "res.partner",
        string="Customer Representative",
        domain="[('parent_id', '=', partner_id)]",
    )
    our_representative_id = fields.Many2one(
        "res.partner",
        string="Our Representative",
        domain="[('is_company', '=', False), ('company_id', '=', company_id)]",
    )
    our_rep_decision_number = fields.Char(string="Our Rep. Decision Number")
    our_rep_decision_date = fields.Date(string="Our Rep. Decision Date")
    date = fields.Date(string="Contract Date", default=fields.Date.context_today)
    contract_type = fields.Selection(
        [("mipyme", "MiPyme"), ("tcp", "TCP"), ("empresa", "Company")],
        string="Contract Type",
        required=True,
    )

    # New Fields
    contract_name = fields.Char(string="Name", required=True, default="/")
    file_number = fields.Char(string="File Number", required=True, default="/")
    start_date = fields.Date(
        string="Start Date", required=True, default=fields.Date.context_today
    )
    end_date = fields.Date(
        string="End Date", required=True, default=fields.Date.context_today
    )
    validity_date = fields.Date(
        string="Validity Date", required=True, default=fields.Date.context_today
    )
    hco = fields.Boolean(string="HCO")
    state = fields.Selection(
        [("pendiente", "Pending"), ("firmado", "Signed")],
        string="Status",
        default="pendiente",
        required=True,
    )

    created_by_id = fields.Many2one(
        "res.users",
        string="Created by",
        default=lambda self: self.env.user,
        readonly=True,
    )
    creation_date_auto = fields.Datetime(
        string="Creation Date", default=fields.Datetime.now, readonly=True
    )
    modification_date_auto = fields.Datetime(
        string="Last Modification", compute="_compute_dates", store=True
    )

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "The Contract Number must be unique. A contract with this number already exists.",
        )
    ]

    @api.depends("write_date")
    def _compute_dates(self):
        for record in self:
            record.modification_date_auto = record.write_date

    def write(self, vals):
        """Prevent editing signed contracts."""
        if any(r.state == "firmado" for r in self) and not self.env.su:
            if not (len(vals) == 1 and "state" in vals):
                raise UserError(_("You cannot edit a signed contract."))
        return super().write(vals)

    def action_sign(self):
        """Transition contract to signed state."""
        for record in self:
            if not record.content:
                raise UserError(
                    _("Please generate the contract content before signing.")
                )
            record.state = "firmado"

    def action_set_to_pending(self):
        """Allow reverting to pending state (admin only)."""
        self.write({"state": "pendiente"})

    content = fields.Html(string="Contract Content")

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            if self.partner_id.classification == "mipyme":
                self.contract_type = "mipyme"
            elif self.partner_id.classification == "tcp":
                self.contract_type = "tcp"
            elif self.partner_id.classification == "empresa":
                self.contract_type = "empresa"

    def action_generate_content(self):
        """Logic to generate contract content from template."""
        # Placeholder for real generation logic
        self.ensure_one()
        template = self.env["contrato.template"].search(
            [("type", "=", self.contract_type)], limit=1
        )
        if not template:
            raise UserError(_("No template found for type %s") % self.contract_type)

        content = template.content
        # Basic replacement simulation
        content = content.replace("{{contract_number}}", self.name or "")
        content = content.replace("{{partner_name}}", self.partner_id.name or "")
        # ... more replacements ...
        self.content = content
