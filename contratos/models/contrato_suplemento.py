import re
from html import unescape

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _plain_text(html: str) -> str:
    """Strip HTML tags and normalize whitespace for comparison."""
    text = unescape(str(html or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


class ContratoSuplemento(models.Model):
    _name = "contrato.suplemento"
    _description = "Suplemento de Contrato Marco"
    _order = "name desc"

    name = fields.Char(
        string="Número de Suplemento",
        required=True,
        default="/",
        readonly=True,
        copy=False,
    )
    marco_id = fields.Many2one(
        "contrato.marco",
        string="Contrato Marco",
        required=True,
        domain=[("state", "=", "firmado")],
        ondelete="restrict",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        related="marco_id.company_id",
        store=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        related="marco_id.partner_id",
        store=True,
    )
    description = fields.Text(string="Descripción de las Modificaciones")
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
    creation_date_auto = fields.Datetime(
        string="Fecha de Creación",
        default=fields.Datetime.now,
        readonly=True,
    )

    # Campos de datos — toman por defecto el valor del contrato marco
    start_date = fields.Date(string="Fecha de Firma")
    start_date_modified = fields.Boolean(
        string="Fecha de Firma Modificada",
        compute="_compute_modified_flags",
        store=True,
        readonly=True,
    )
    validity_years = fields.Integer(string="Tiempo de Validez")
    validity_years_modified = fields.Boolean(
        string="Tiempo de Validez Modificado",
        compute="_compute_modified_flags",
        store=True,
        readonly=True,
    )
    content = fields.Html(string="Contenido del Contrato")
    content_modified = fields.Boolean(
        string="Contenido Modificado",
        compute="_compute_modified_flags",
        store=True,
        readonly=True,
    )

    @api.depends(
        "marco_id",
        "marco_id.start_date",
        "marco_id.validity_years",
        "marco_id.content",
        "start_date",
        "validity_years",
        "content",
    )
    def _compute_modified_flags(self) -> None:
        for record in self:
            if not record.marco_id:
                record.start_date_modified = False
                record.validity_years_modified = False
                record.content_modified = False
                continue
            record.start_date_modified = record.start_date != record.marco_id.start_date
            record.validity_years_modified = (
                record.validity_years != record.marco_id.validity_years
            )
            expected = '<h3 style="text-align:center;">(Suplemento)</h3>\n' + unescape(
                str(record.marco_id.content or "")
            )
            record.content_modified = _plain_text(record.content) != _plain_text(
                expected
            )

    @api.onchange("marco_id")
    def _onchange_marco_id(self) -> None:
        if self.marco_id:
            marco = self.marco_id
            self.start_date = marco.start_date
            self.validity_years = marco.validity_years
            raw_content = unescape(str(marco.content or ""))
            self.content = (
                '<h3 style="text-align:center;">(Suplemento)</h3>\n' + raw_content
            )

    @staticmethod
    def _replace_date_in_content(content: str, old_date, new_date) -> str:
        """Reemplaza day/month/year embebidos en el HTML al cambiar la fecha de firma.

        Usa regex en lugar de coincidencia exacta para resistir variaciones
        en el atributo style introducidas por el sanitizador HTML de Odoo.
        """

        def replace_highlighted(html: str, old_val: str, new_val: str) -> str:
            pattern = re.compile(
                r"(<strong\b[^>]*>)\s*" + re.escape(old_val) + r"\s*(</strong>)",
                re.IGNORECASE,
            )
            return pattern.sub(rf"\g<1>{new_val}\2", html)

        if old_date.day != new_date.day:
            content = replace_highlighted(
                content, str(old_date.day), str(new_date.day)
            )
        if old_date.strftime("%B") != new_date.strftime("%B"):
            content = replace_highlighted(
                content, old_date.strftime("%B"), new_date.strftime("%B")
            )
        if old_date.year != new_date.year:
            content = replace_highlighted(
                content, str(old_date.year), str(new_date.year)
            )
        return content

    @api.onchange("start_date")
    def _onchange_start_date(self) -> None:
        """Actualiza las variables day/month/year en el contenido al cambiar la fecha de inicio."""
        if not self.marco_id or not self.start_date or not self.content:
            return

        old_date = self._origin.start_date or self.marco_id.start_date
        if not old_date or old_date == self.start_date:
            return

        updated = self._replace_date_in_content(
            str(self.content), old_date, self.start_date
        )
        self.content = Markup(updated)

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> "ContratoSuplemento":
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("contrato.suplemento.sequence")
                    or "/"
                )
        return super().create(vals_list)

    # Fields managed by the ORM (computed stored) that can be written on firmado records
    _SYSTEM_WRITE_ALLOWED = frozenset(
        [
            "state",
            "signed_by_id",
            "signing_date",
            "start_date_modified",
            "validity_years_modified",
            "content_modified",
        ]
    )

    def write(self, vals: dict) -> bool:
        """Prevent editing signed supplements. Sync date variables in content when start_date changes."""
        if any(r.state == "firmado" for r in self) and not self.env.su:
            if not vals.keys() <= self._SYSTEM_WRITE_ALLOWED:
                raise UserError(_("No puede editar un suplemento firmado."))

        if "start_date" not in vals or not vals.get("start_date"):
            return super().write(vals)

        new_date = fields.Date.from_string(vals["start_date"])

        # Read pre-write start_date directly from DB to bypass any ORM cache ambiguity.
        # (record.start_date inside write() could return the new value from the ORM
        # pending-write cache in some Odoo versions.)
        self.env.cr.execute(
            "SELECT id, start_date FROM contrato_suplemento WHERE id = ANY(%s)",
            (self.ids,),
        )
        old_start_dates = {row[0]: row[1] for row in self.env.cr.fetchall()}

        # Apply the standard write first (includes content from onchange if present in vals)
        result = super().write(vals)

        # After the write the ORM cache is invalidated, so record.content now reflects
        # what was actually stored (sanitized HTML from Odoo's Html field).
        # Apply the date regex replacement only when the content still has the old date
        # (handles the case where the onchange didn't run or didn't update the content).
        for record in self:
            old_date = old_start_dates.get(record.id)
            if not old_date or old_date == new_date or not record.content:
                continue
            current_content = str(record.content)
            updated = self._replace_date_in_content(current_content, old_date, new_date)
            if updated != current_content:
                # Bypass our override to avoid re-triggering the date-sync logic
                super(ContratoSuplemento, record).write({"content": Markup(updated)})

        return result

    def action_sign(self) -> None:
        """Transition borrador → entregado."""
        for record in self:
            if record.state not in ("borrador", "cancelado"):
                raise UserError(
                    _("Solo se pueden entregar suplementos en borrador o cancelados.")
                )
            record.write(
                {
                    "state": "entregado",
                    "signed_by_id": self.env.user.partner_id.id,
                    "signing_date": fields.Datetime.now(),
                }
            )

    def action_entregar(self) -> None:
        """Transition entregado → firmado."""
        for record in self:
            if record.state != "entregado":
                raise UserError(_("Solo se pueden firmar suplementos entregados."))
            record.write({"state": "firmado"})

    def action_draft_from_entregado(self) -> None:
        """Revert entregado → borrador."""
        for record in self:
            if record.state != "entregado":
                raise UserError(
                    _("Solo se puede retroceder a Borrador desde Entregado.")
                )
            record.write({"state": "borrador"})

    def action_cancel(self) -> None:
        """Cancel the supplement."""
        for record in self:
            record.write({"state": "cancelado"})

    def action_draft(self) -> None:
        """Revert cancelado → borrador."""
        for record in self:
            record.write({"state": "borrador"})
