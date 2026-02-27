import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerOrganism(models.Model):
    _name = "res.partner.organism"
    _description = "Organism"

    name = fields.Char(string="Name", required=True)


class ResPartner(models.Model):
    _inherit = "res.partner"

    classification = fields.Selection(
        [
            ("mipyme", "Mipyme"),
            ("tcp", "TCP"),
            ("empresa", "Company"),
            ("presupuestada", "State-funded"),
        ],
        string="Classification",
    )

    organism_id = fields.Many2one("res.partner.organism", string="Organism")
    short_name = fields.Char(string="Abbreviated Name")
    titular = fields.Char(string="Bank Account Holder")
    id_card = fields.Char(string="ID Card")

    # Representation Fields
    represented_by_id = fields.Many2one("res.partner", string="Represented by")
    appointed_by_agreement = fields.Char(string="Appointed by Agreement No")
    appointment_date = fields.Date(string="Appointment Date")

    # Resolution Fields
    resolution_number = fields.Char(string="Creation Resolution Number")
    creation_date = fields.Date(string="Creation Resolution Date")
    issued_by = fields.Char(string="Issued by (Creation)")
    current_resolution_number = fields.Char(string="Signer's Resolution Number")
    current_creation_date = fields.Date(string="Signer's Resolution Date")
    current_issued_by = fields.Char(string="Issued by (Signer)")

    # MiPyme Registration Fields
    notary_deed_number = fields.Char(string="Notary Deed Number")
    mercantile_register = fields.Char(string="Mercantile Register")
    register_volume = fields.Char(string="Volume")
    register_page = fields.Char(string="Page")
    register_sheet = fields.Char(string="Sheet")

    reeup = fields.Char(string="REEUP")
    tax_id = fields.Char(string="NIT")
    bank_account_cup = fields.Char(string="CUP Account")
    bank_account_mlc = fields.Char(string="MLC Account")
    bank_branch_number = fields.Char(string="Bank Branch Number (CUP)")

    # MiPyme Bank Branch Fields
    bank_cup_branch = fields.Char(string="MiPyme Branch (CUP)")
    bank_mlc_branch = fields.Char(string="MiPyme Branch (MLC)")

    # TCP Bank Branch Fields
    tcp_bank_cup_branch = fields.Char(string="TCP Branch (CUP)")
    tcp_bank_mlc_branch = fields.Char(string="TCP Branch (MLC)")

    bank_id_ref = fields.Many2one(
        "res.partner", string="Bank", domain=[("is_company", "=", True)]
    )

    @api.onchange("reeup", "classification")
    def _onchange_reeup_mipyme(self):
        if self.classification == "mipyme" and self.reeup:
            self.tax_id = self.reeup

    @api.onchange("tax_id", "classification")
    def _onchange_tax_id_mipyme(self):
        if self.classification == "mipyme" and self.tax_id:
            self.reeup = self.tax_id

    @api.constrains("reeup", "tax_id", "classification")
    def _check_reeup_tax_id_mipyme(self):
        for record in self:
            if record.classification == "mipyme":
                if record.reeup != record.tax_id:
                    raise ValidationError(
                        "For MiPymes, REEUP and NIT must be the same."
                    )

    @api.constrains("id_card")
    def _check_id_card_format(self):
        for record in self:
            if record.id_card:
                if not re.match(r"^\d{11}$", record.id_card):
                    raise ValidationError("The ID Card must contain exactly 11 digits.")
            if record.is_company and record.id_card:
                raise ValidationError("Companies cannot have an ID Card (CI).")
