from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContratoMarco(models.Model):
    _name = "contrato.marco"
    _description = "Contrato Marco"

    name = fields.Char(string="Número de Contrato", required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        domain=[("is_company", "=", True)],
    )
    representative_id = fields.Many2one(
        "res.partner",
        string="Representante del Cliente",
        domain="[('parent_id', '=', partner_id)]",
    )
    our_representative_id = fields.Many2one(
        "res.partner",
        string="Nuestro Representante",
        domain="[('is_company', '=', False), ('company_id', '=', company_id)]",
    )
    our_rep_decision_number = fields.Char(string="Número de Resolución del Rep.")
    our_rep_decision_date = fields.Date(string="Fecha de Resolución del Rep.")
    date = fields.Date(string="Fecha del Contrato", default=fields.Date.context_today)
    contract_type = fields.Selection(
        [("mipyme", "MiPyme"), ("tcp", "TCP"), ("empresa", "Empresa")],
        string="Tipo de Contrato",
        required=True,
    )

    # New Fields
    contract_name = fields.Char(string="Nombre", required=True, default="/")
    file_number = fields.Char(string="Número de Expediente", required=True, default="/")
    start_date = fields.Date(
        string="Fecha de Inicio", required=True, default=fields.Date.context_today
    )
    end_date = fields.Date(
        string="Fecha de Fin", required=True, default=fields.Date.context_today
    )
    validity_date = fields.Date(
        string="Fecha de Vigencia", required=True, default=fields.Date.context_today
    )
    hco = fields.Boolean(string="HCO")
    oeb = fields.Char(string="OEB")
    state = fields.Selection(
        [
            ("borrador", "Borrador"),
            ("firmado", "Firmado"),
            ("cancelado", "Cancelado"),
        ],
        string="Estado",
        default="borrador",
        required=True,
        copy=False,
    )

    authorized_contact_ids = fields.Many2many(
        "res.partner",
        string="Contactos Autorizados",
        domain="[('is_company', '=', False), ('company_id', '=', company_id)]",
        help="Contactos de nuestra empresa autorizados para firmar este contrato.",
    )
    signed_by_id = fields.Many2one(
        "res.partner",
        string="Firmado por",
        readonly=True,
        copy=False,
    )
    signing_date = fields.Datetime(
        string="Fecha de Firma",
        readonly=True,
        copy=False,
    )

    created_by_id = fields.Many2one(
        "res.users",
        string="Creado por",
        default=lambda self: self.env.user,
        readonly=True,
    )
    creation_date_auto = fields.Datetime(
        string="Fecha de Creación", default=fields.Datetime.now, readonly=True
    )
    modification_date_auto = fields.Datetime(
        string="Última Modificación", compute="_compute_dates", store=True
    )

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "El Número de Contrato debe ser único. Ya existe un contrato con este número.",
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
                raise UserError(_("No puede editar un contrato firmado."))
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
                raise UserError(
                    _("Solo se pueden firmar contratos en borrador o cancelados.")
                )

            if not record.content:
                raise UserError(
                    _("Por favor, genere el contenido del contrato antes de firmar.")
                )

            # Authorization Check
            user_partner = self.env.user.partner_id
            if (
                user_partner not in record.authorized_contact_ids
                and not self.env.is_admin()
            ):
                raise UserError(
                    _("Solo los contactos autorizados pueden firmar este contrato.")
                )

            record.write(
                {
                    "state": "firmado",
                    "signed_by_id": user_partner.id,
                    "signing_date": fields.Datetime.now(),
                }
            )

    content = fields.Html(string="Contenido del Contrato")

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
            raise UserError(
                _("No se encontró ninguna plantilla para el tipo %s")
                % self.contract_type
            )

        content = template.content
        # Basic replacement simulation
        content = content.replace("{{contract_number}}", self.name or "")
        content = content.replace("{{partner_name}}", self.partner_id.name or "")
        # ... more replacements ...
        self.content = content
