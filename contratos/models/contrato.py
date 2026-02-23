from odoo import api, fields, models


class ContratoMarco(models.Model):
    _name = "contrato.marco"
    _description = "Master Contract"

    name = fields.Char(string="Contract Number", required=True)
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
        domain=[("is_company", "=", False)],
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
