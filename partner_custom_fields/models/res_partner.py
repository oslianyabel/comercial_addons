import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerOrganism(models.Model):
    _name = "res.partner.organism"
    _description = "Organismo"

    name = fields.Char(string="Nombre", required=True)


class ResPartnerUEB(models.Model):
    _name = "res.partner.ueb"
    _description = "UEB"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", required=True)
    active = fields.Boolean(default=True)
    partner_ids = fields.Many2many(
        "res.partner",
        compute="_compute_partner_ids",
        inverse="_inverse_partner_ids",
        string="Contactos",
        domain="[('is_company', '=', True)]",
    )
    partner_count = fields.Integer(
        string="Nº de contactos",
        compute="_compute_partner_count",
    )

    def _compute_partner_ids(self):
        for rec in self:
            rec.partner_ids = self.env["res.partner"].search([("ueb_id", "=", rec.id)])

    def _inverse_partner_ids(self):
        for rec in self:
            old_partners = self.env["res.partner"].search([("ueb_id", "=", rec.id)])
            removed = old_partners - rec.partner_ids
            removed.write({"ueb_id": False})
            rec.partner_ids.write({"ueb_id": rec.id})

    def _compute_partner_count(self):
        for rec in self:
            rec.partner_count = self.env["res.partner"].search_count(
                [("ueb_id", "=", rec.id)]
            )


class ResPartner(models.Model):
    _inherit = "res.partner"

    classification = fields.Selection(
        [
            ("mipyme", "Mipyme"),
            ("tcp", "TCP"),
            ("empresa", "Empresa"),
            ("presupuestada", "Presupuestada"),
        ],
        string="Clasificación",
    )

    organism_id = fields.Many2one("res.partner.organism", string="Organismo")
    short_name = fields.Char(string="Nombre Abreviado")
    titular = fields.Char(string="Titular de Cuenta Bancaria")
    id_card = fields.Char(string="Carnet de Identidad")
    ueb_id = fields.Many2one("res.partner.ueb", string="UEB")

    # Representation Fields
    represented_by_id = fields.Many2one("res.partner", string="Representado por")
    appointed_by_agreement = fields.Char(string="Designado por Acuerdo No")
    appointment_date = fields.Date(string="Fecha de Designación")

    # Resolution Fields
    resolution_number = fields.Char(string="Número de Resolución de Creación")
    creation_date = fields.Date(string="Fecha de Resolución de Creación")
    issued_by = fields.Char(string="Emitido por (Creación)")
    current_resolution_number = fields.Char(string="Número de Resolución del Firmante")
    current_creation_date = fields.Date(string="Fecha de Resolución del Firmante")
    current_issued_by = fields.Char(string="Emitido por (Firmante)")

    # MiPyme Registration Fields
    notary_deed_number = fields.Char(string="Número de Escritura Notarial")
    mercantile_register = fields.Char(string="Registro Mercantil")
    register_volume = fields.Char(string="Tomo")
    register_page = fields.Char(string="Folio")
    register_sheet = fields.Char(string="Hoja")

    reeup = fields.Char(string="REEUP")
    tax_id = fields.Char(string="NIT")
    bank_account_cup = fields.Char(string="Cuenta CUP")
    bank_account_mlc = fields.Char(string="Cuenta MLC")
    bank_branch_number = fields.Char(string="Número de Sucursal Bancaria (CUP)")

    # MiPyme Bank Branch Fields
    bank_cup_branch = fields.Char(string="Sucursal MiPyme (CUP)")
    bank_mlc_branch = fields.Char(string="Sucursal MiPyme (MLC)")

    # TCP Bank Branch Fields
    tcp_bank_cup_branch = fields.Char(string="Sucursal TCP (CUP)")
    tcp_bank_mlc_branch = fields.Char(string="Sucursal TCP (MLC)")

    bank_id_ref = fields.Many2one(
        "res.partner", string="Banco", domain=[("is_company", "=", True)]
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
                        "Para MiPymes, el REEUP y el NIT deben ser iguales."
                    )

    @api.constrains("id_card")
    def _check_id_card_format(self):
        for record in self:
            if record.id_card:
                if not re.match(r"^\d{11}$", record.id_card):
                    raise ValidationError(
                        "El Carnet de Identidad debe contener exactamente 11 dígitos."
                    )
            if record.is_company and record.id_card:
                raise ValidationError(
                    "Las empresas no pueden tener Carnet de Identidad (CI)."
                )
