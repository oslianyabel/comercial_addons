import re
from datetime import date as pydate
from html import unescape

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class ContratoMarco(models.Model):
    _name = "contrato.marco"
    _description = "Contrato Marco"

    name = fields.Char(string="Número de Contrato", required=True, default="/")
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
    contract_type = fields.Selection(
        [("mipyme", "MiPyme"), ("tcp", "TCP"), ("empresa", "Empresa")],
        string="Tipo de Contrato",
        required=True,
    )

    contract_name = fields.Char(string="Nombre", required=True)
    start_date = fields.Date(
        string="Fecha de Firma", required=True, default=fields.Date.context_today
    )
    validity_years = fields.Integer(
        string="Tiempo de Validez",
        required=True,
        default=lambda self: self._default_validity_years(),
    )
    end_date = fields.Date(
        string="Fecha de Finalización",
        compute="_compute_end_date",
        store=True,
    )
    validity_date = fields.Date(
        string="Fecha de Vigencia",
        default=fields.Date.context_today,
    )
    oeb = fields.Char(string="OEB (Organismo de Base)")
    state = fields.Selection(
        [
            ("borrador", "Borrador"),
            ("entregado", "Entregado"),
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
        string="Fecha de Entrega",
        readonly=True,
        copy=False,
    )

    created_by_id = fields.Many2one(
        "res.users",
        string="Creado por",
        default=lambda self: self.env.user,
        readonly=True,
    )
    suplemento_ids = fields.One2many(
        "contrato.suplemento",
        "marco_id",
        string="Suplementos",
    )
    suplemento_count = fields.Integer(
        string="Nº Suplementos",
        compute="_compute_suplemento_count",
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

    @api.depends("name", "partner_id")
    @api.depends_context("display_partner_name")
    def _compute_display_name(self):
        if self.env.context.get("display_partner_name"):
            for record in self:
                record.display_name = record.partner_id.name or record.name or ""
            return
        super()._compute_display_name()

    @api.depends("write_date")
    def _compute_dates(self):
        for record in self:
            record.modification_date_auto = record.write_date

    @api.depends("suplemento_ids")
    def _compute_suplemento_count(self):
        for record in self:
            record.suplemento_count = len(record.suplemento_ids)

    @api.depends("start_date", "validity_years")
    def _compute_end_date(self):
        for record in self:
            if record.start_date and record.validity_years:
                record.end_date = record._add_years(
                    record.start_date, record.validity_years
                )
            else:
                record.end_date = False

    @api.model
    def _default_validity_years(self):
        param_value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("contratos.master_contract_validity_years", default="5")
        )
        try:
            return int(param_value)
        except (TypeError, ValueError):
            return 5

    @staticmethod
    def _add_years(value, years):
        if not value or not years:
            return value
        try:
            return value.replace(year=value.year + years)
        except ValueError:
            if value.month == 2 and value.day == 29:
                return pydate(value.year + years, 2, 28)
            raise

    def name_get(self):
        return [
            (record.id, record.partner_id.name or record.name or "") for record in self
        ]

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
                    [("contract_name", operator, name)],
                    [("partner_id.name", operator, name)],
                ]
            )
            domain = expression.AND([domain, search_domain])
        return self._search(
            domain,
            limit=limit,
            access_rights_uid=name_get_uid,
            order=order,
        )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        self.update({"representative_id": False})
        if self.partner_id and self.partner_id.classification:
            self.contract_type = self.partner_id.classification
        else:
            self.contract_type = False
            if self.partner_id:
                return {
                    "warning": {
                        "title": _("Cliente sin Clasificación"),
                        "message": _(
                            "El cliente '%s' no tiene una Clasificación configurada. "
                            "Debe establecer la Clasificación del cliente antes de crear el contrato."
                        )
                        % self.partner_id.name,
                    }
                }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("validity_years"):
                vals["validity_years"] = self._default_validity_years()
            if not vals.get("contract_type") and vals.get("partner_id"):
                partner = self.env["res.partner"].browse(vals["partner_id"])
                if partner.classification:
                    vals["contract_type"] = partner.classification
                else:
                    raise UserError(
                        _(
                            "El cliente '%s' no tiene una Clasificación configurada (MiPyme, TCP, Empresa, etc.). "
                            "Establezca la Clasificación del cliente antes de crear el contrato."
                        )
                        % partner.name
                    )
            if not vals.get("name") or vals.get("name") == "/":
                sequence_date = vals.get("start_date") or fields.Date.context_today(
                    self
                )
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "contrato.marco.sequence",
                        sequence_date=sequence_date,
                    )
                    or "/"
                )
        return super().create(vals_list)

    def write(self, vals):
        """Prevent editing signed contracts. Delivered contracts remain editable."""
        if any(r.state == "firmado" for r in self) and not self.env.su:
            if not (len(vals) == 1 and "state" in vals):
                raise UserError(_("No puede editar un contrato firmado."))
        if "partner_id" in vals:
            vals["representative_id"] = False
        return super().write(vals)

    @api.constrains("partner_id", "representative_id")
    def _check_representative_belongs_to_partner(self):
        for record in self:
            if record.representative_id and record.partner_id:
                if record.representative_id.parent_id != record.partner_id:
                    raise UserError(
                        _(
                            "El representante '%s' no pertenece al cliente '%s'. "
                            "Seleccione un representante que sea contacto del cliente elegido."
                        )
                        % (
                            record.representative_id.name,
                            record.partner_id.display_name,
                        )
                    )

    @api.constrains("partner_id")
    def _check_unique_partner_contract(self):
        for record in self:
            if not record.partner_id:
                continue
            duplicated_count = self.search_count(
                [
                    ("id", "!=", record.id),
                    ("partner_id", "=", record.partner_id.id),
                ]
            )
            if duplicated_count:
                raise UserError(
                    _(
                        "Solo puede existir un contrato marco por cliente. Ya existe un contrato marco para '%s'."
                    )
                    % record.partner_id.display_name
                )

    def action_draft(self):
        """Revert to draft state."""
        for record in self:
            record.write({"state": "borrador"})

    def action_cancel(self):
        """Cancel the contract."""
        for record in self:
            specific_contracts = self.env["contrato.especifico"].search(
                [
                    ("marco_id", "=", record.id),
                    ("state", "!=", "cancelado"),
                ]
            )
            if specific_contracts:
                specific_contracts.with_context(from_master_cancel=True).action_cancel()
            record.write({"state": "cancelado"})

    def action_entregar(self):
        """Transition contract to signed state (final active state)."""
        for record in self:
            if record.state != "entregado":
                raise UserError(_("Solo se pueden firmar contratos entregados."))
            record.write({"state": "firmado"})

    def action_draft_from_entregado(self):
        """Revert contract from delivered back to draft."""
        for record in self:
            if record.state != "entregado":
                raise UserError(
                    _("Solo se puede retroceder a Borrador desde Entregado.")
                )
            record.write({"state": "borrador"})

    def action_sign(self):
        """Transition contract to delivered state with authorization check."""
        for record in self:
            if record.state not in ["borrador", "cancelado"]:
                raise UserError(
                    _("Solo se pueden entregar contratos en borrador o cancelados.")
                )

            if not record._has_generated_content():
                raise UserError(
                    _("Por favor, genere el contenido del contrato antes de entregar.")
                )

            # Authorization Check
            user_partner = self.env.user.partner_id
            if (
                user_partner not in record.authorized_contact_ids
                and not self.env.is_admin()
            ):
                raise UserError(
                    _("Solo los contactos autorizados pueden entregar este contrato.")
                )

            record.write(
                {
                    "state": "entregado",
                    "signed_by_id": user_partner.id,
                    "signing_date": fields.Datetime.now(),
                }
            )

    content = fields.Html(string="Contenido del Contrato")

    def _has_generated_content(self):
        self.ensure_one()
        if not self.content:
            return False

        plain_content = unescape(str(self.content or ""))
        plain_content = re.sub(r"<[^>]+>", " ", plain_content)
        plain_content = plain_content.replace("&nbsp;", " ")
        plain_content = re.sub(r"\s+", " ", plain_content).strip()
        return bool(plain_content)

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            if self.partner_id.classification == "mipyme":
                self.contract_type = "mipyme"
            elif self.partner_id.classification == "tcp":
                self.contract_type = "tcp"
            elif self.partner_id.classification == "empresa":
                self.contract_type = "empresa"

    @api.onchange("start_date")
    def _onchange_start_date(self):
        if self.start_date and not self.end_date:
            self.end_date = self._add_years(self.start_date, self.validity_years or 0)

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

    def action_open_suplementos(self):
        """Open the list of supplements related to this master contract."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Suplementos"),
            "res_model": "contrato.suplemento",
            "view_mode": "tree,form",
            "domain": [("marco_id", "=", self.id)],
            "context": {"default_marco_id": self.id},
        }

    def action_crear_suplemento(self):
        """Open a new supplement form pre-linked to this master contract."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nuevo Suplemento"),
            "res_model": "contrato.suplemento",
            "view_mode": "form",
            "context": {"default_marco_id": self.id},
        }
