import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.osv import expression


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

    vat = fields.Char(string="NIT")

    organism_id = fields.Many2one("res.partner.organism", string="Organismo")
    short_name = fields.Char(string="Nombre Abreviado")
    titular = fields.Char(string="Titular de Cuenta Bancaria")
    id_card = fields.Char(string="Carnet de Identidad")
    ueb_id = fields.Many2one("res.partner.ueb", string="UEB")
    ueb_ids = fields.Many2many(
        "res.partner.ueb",
        compute="_compute_ueb_ids",
        string="UEBs",
    )

    @api.depends("ueb_id")
    def _compute_ueb_ids(self) -> None:
        for rec in self:
            rec.ueb_ids = rec.ueb_id if rec.ueb_id else self.env["res.partner.ueb"]

    position = fields.Char(string="Position")

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
    customer_number = fields.Char(string="Número de Cliente")
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

    @api.constrains("is_company")
    def _check_is_company_not_linked_to_contrato(self):
        for record in self:
            if not record.is_company:
                contrato = self.env["contrato.marco"].search(
                    [("partner_id", "=", record.id)], limit=1
                )
                if contrato:
                    raise ValidationError(
                        _(
                            "No puede cambiar el tipo de contacto de '%s' porque está asociado al "
                            "contrato marco '%s'. Elimine el contrato marco antes de realizar este cambio."
                        )
                        % (record.name, contrato.name)
                    )

    @api.constrains("reeup", "is_company")
    def _check_unique_company_reeup(self):
        for record in self:
            if not record.is_company or not record.reeup:
                continue

            duplicated_count = self.search_count(
                [
                    ("id", "!=", record.id),
                    ("is_company", "=", True),
                    ("reeup", "=", record.reeup),
                ]
            )
            if duplicated_count:
                raise ValidationError(
                    _("El REEUP debe ser único entre los contactos de tipo compañía.")
                )

    @api.model
    def _name_search(
        self,
        name="",
        args=None,
        operator="ilike",
        limit=100,
        name_get_uid=None,
        order=None,
    ):
        domain = args or []
        if name:
            search_domain = expression.OR(
                [
                    [("name", operator, name)],
                    [("reeup", operator, name)],
                    [("customer_number", operator, name)],
                ]
            )
            domain = expression.AND([domain, search_domain])
        return self._search(
            domain,
            limit=limit,
            access_rights_uid=name_get_uid,
            order=order,
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
