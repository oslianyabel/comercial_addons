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
        [("mipyme", "MiPyme"), ("tcp", "TCP"), ("empresa", "Empresa")],
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
    oeb = fields.Char(string="OEB")
    state = fields.Selection(
        [
            ("borrador", "Draft"),
            ("firmado", "Signed"),
            ("cancelado", "Cancelled"),
        ],
        string="Status",
        default="borrador",
        required=True,
        copy=False,
    )

    authorized_contact_ids = fields.Many2many(
        "res.partner",
        string="Authorized Contacts",
        domain="[('is_company', '=', False), ('company_id', '=', company_id)]",
        help="Contacts from our company authorized to sign this contract.",
    )
    signed_by_id = fields.Many2one(
        "res.partner",
        string="Signed by",
        readonly=True,
        copy=False,
    )
    signing_date = fields.Datetime(
        string="Signing Date",
        readonly=True,
        copy=False,
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

    def action_draft(self):
        """Revert to draft state."""
        for record in self:
            record.write({"state": "borrador"})

    def action_cancel(self):
        """Cancel the contract."""
        for record in self:
            record.write({"state": "cancelado"})

    def action_sign(self):
        """Transition contract to signed state with authorization check."""
        for record in self:
            if record.state not in ["borrador", "cancelado"]:
                raise UserError(_("Only draft or cancelled contracts can be signed."))

            if not record.content:
                raise UserError(
                    _("Please generate the contract content before signing.")
                )

            # Authorization Check
            user_partner = self.env.user.partner_id
            if (
                user_partner not in record.authorized_contact_ids
                and not self.env.is_admin()
            ):
                raise UserError(_("Only authorized contacts can sign this contract."))

            record.write(
                {
                    "state": "firmado",
                    "signed_by_id": user_partner.id,
                    "signing_date": fields.Datetime.now(),
                }
            )

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
