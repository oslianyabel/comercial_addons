import os
import re
from html import unescape

from markupsafe import Markup

from odoo import _, models
from odoo.exceptions import UserError


class ContratoMarco(models.Model):
    _inherit = "contrato.marco"

    _CONTENT_FIELDS = frozenset(
        [
            "partner_id",
            "representative_id",
            "our_representative_id",
            "our_rep_decision_number",
            "our_rep_decision_date",
            "start_date",
            "validity_years",
            "contract_type",
            "oeb",
        ]
    )

    # Fields that, when changed on a firmado contract, trigger suplemento auto-creation
    _SUPLEMENTO_TRACKED_FIELDS = frozenset(
        [
            "representative_id",
            "our_representative_id",
            "authorized_contact_ids",
            "our_rep_decision_number",
            "our_rep_decision_date",
            "start_date",
            "validity_years",
        ]
    )

    _SUPLEMENTO_FIELD_LABELS = {
        "representative_id": "Representante del Cliente",
        "our_representative_id": "Nuestro Representante",
        "authorized_contact_ids": "Contactos Autorizados",
        "our_rep_decision_number": "Acuerdo/Decisión",
        "our_rep_decision_date": "Fecha de Resolución del Rep",
        "start_date": "Fecha de Firma",
        "validity_years": "Tiempo de Validez",
    }

    def _build_content_html(self, overrides=None):
        """Generate and return the HTML content string for this contract record.

        overrides: optional dict mapping field_name → value (Many2one as recordset,
        scalar fields as plain values). When provided, those values take priority
        over the record's own field values.  Used for suplemento content generation.
        """
        self.ensure_one()
        if overrides is None:
            overrides = {}

        def get(field):
            """Return override value if present, otherwise record's field value."""
            if field in overrides:
                return overrides[field]
            return getattr(self, field)

        # 1. Try to get template from DB first
        contract_type = get("contract_type")
        template = self.env["contrato.template"].search(
            [("type", "=", contract_type)], limit=1
        )
        content = ""

        if template:
            content = unescape(str(template.content or ""))
        else:
            # Fallback to Filesystem
            template_name = ""
            if contract_type == "mipyme":
                template_name = "contrato marco Mipyme.txt"
            elif contract_type == "tcp":
                template_name = "contrato marco TCP.txt"
            elif contract_type == "empresa":
                template_name = "contrato marco empresas.txt"

            if template_name:
                base_path = "c:\\Users\\lilia\\Desktop\\Projects\\Odoo\\instancias\\odoo17_comercial2\\extra_addons\\context\\"
                template_path = os.path.join(base_path, template_name)
                if os.path.exists(template_path):
                    with open(template_path, "r", encoding="utf-8") as f:
                        raw_content = f.read()
                        content = self.env["contrato.template"]._format_to_html(
                            raw_content
                        )
                        existing = self.env["contrato.template"].search(
                            [("type", "=", contract_type)], limit=1
                        )
                        if not existing:
                            self.env["contrato.template"].create(
                                {
                                    "name": template_name.replace(
                                        ".txt", ""
                                    ).capitalize(),
                                    "type": contract_type,
                                    "content": content,
                                }
                            )

        if not content:
            raise UserError(
                _(
                    "No template found for this contract type (Database or Filesystem)."
                )
            )

        # Replacement logic (Unified variable mapper)
        p = self.partner_id
        r = get("representative_id") or p.represented_by_id
        our_r = get("our_representative_id")

        comp = (
            self.env["res.company"].search(
                [("name", "ilike", "Soluciones DTeam")], limit=1
            )
            or self.env.company
        )
        comp_partner = comp.partner_id

        # Validation
        missing = []
        if not our_r:
            missing.append(_("Nuestro Representante"))
        elif not our_r.position:
            missing.append(_("Nuestro Representante: Cargo"))
        if not get("our_rep_decision_number"):
            missing.append(_("Nuestro Rep. Número de Resolución"))
        if not get("our_rep_decision_date"):
            missing.append(_("Nuestro Rep. Fecha de Resolución"))
        if not r:
            missing.append(_("Representante del Cliente"))

        req_p = [
            "tax_id",
            "reeup",
            "bank_account_cup",
            "phone",
            "email",
            "street",
            "city",
        ]
        if contract_type == "empresa":
            req_p += [
                "short_name",
                "organism_id",
                "resolution_number",
                "creation_date",
                "issued_by",
                "bank_branch_number",
                "bank_id_ref",
                "current_resolution_number",
                "current_creation_date",
                "current_issued_by",
            ]
        elif contract_type == "mipyme":
            req_p += [
                "notary_deed_number",
                "mercantile_register",
                "register_volume",
                "register_page",
                "register_sheet",
                "bank_account_mlc",
                "bank_mlc_branch",
                "bank_id_ref",
                "appointed_by_agreement",
                "appointment_date",
            ]
        elif contract_type == "tcp":
            req_p += [
                "id_card",
                "bank_account_mlc",
                "tcp_bank_mlc_branch",
                "bank_account_cup",
                "tcp_bank_cup_branch",
                "bank_id_ref",
            ]

        for f in req_p:
            if not getattr(p, f):
                missing.append(_("Cliente: %s") % _(p._fields[f].string))
        if not comp_partner.titular:
            missing.append(_("Compañía: Titular de Cuenta Bancaria"))

        if missing:
            raise UserError(
                _(
                    "The contract cannot be generated because the following data is missing:\n\n- %s"
                )
                % "\n- ".join(missing)
            )

        def highlight(val):
            return f'<strong style="font-weight: bold; text-decoration: underline; color: #000080;">{val or ""}</strong>'

        def fmt_date(d):
            return (
                highlight(d.strftime("%d/%m/%Y"))
                if d
                else highlight("__________________")
            )

        address = " ".join(
            [f for f in [p.street, p.street2, p.city, p.state_id.name] if f]
        )

        start_date = get("start_date")
        oeb = get("oeb")

        # Building the universal variable dictionary
        template_vals = {
            "contract_number": highlight(self.name),
            "our_email": highlight(comp_partner.email),
            "our_representative": highlight(our_r.name),
            "our_rep_position": highlight(our_r.position),
            "our_rep_decision_number": highlight(get("our_rep_decision_number")),
            "our_rep_decision_date": fmt_date(get("our_rep_decision_date")),
            "partner_name": highlight(p.name),
            "partner_via": highlight(oeb) if oeb else "",
            "partner_oeb": highlight(oeb) if oeb else "",
            "partner_short_name": highlight(p.short_name),
            "partner_organism": highlight(p.organism_id.name),
            "partner_resolution_number": highlight(p.resolution_number),
            "partner_creation_date": fmt_date(p.creation_date),
            "partner_issued_by": highlight(p.issued_by),
            "partner_address": highlight(address),
            "partner_reeup": highlight(p.reeup),
            "partner_bank_account_cup": highlight(p.bank_account_cup),
            "partner_bank_branch": highlight(p.bank_branch_number),
            "partner_bank_name": highlight(p.bank_id_ref.name),
            "partner_bank_address": highlight(p.bank_id_ref.street),
            "partner_titular": highlight(comp_partner.titular),
            "partner_phone": highlight(p.phone),
            "partner_email": highlight(p.email),
            "partner_tax_id": highlight(p.tax_id),
            "partner_representative": highlight(r.name),
            "partner_rep_function": highlight(r.function),
            "partner_current_resolution": highlight(p.current_resolution_number),
            "partner_current_date": fmt_date(p.current_creation_date),
            "partner_current_issued_by": highlight(p.current_issued_by),
            "day": highlight(start_date.day if start_date else ""),
            "month": highlight(start_date.strftime("%B") if start_date else ""),
            "year": highlight(start_date.year if start_date else ""),
        }

        if contract_type == "mipyme":
            template_vals.update(
                {
                    "notary_deed_number": highlight(p.notary_deed_number),
                    "mercantile_register": highlight(p.mercantile_register),
                    "register_volume": highlight(p.register_volume),
                    "register_page": highlight(p.register_page),
                    "register_sheet": highlight(p.register_sheet),
                    "bank_account_mlc": highlight(p.bank_account_mlc),
                    "bank_mlc_branch": highlight(p.bank_mlc_branch),
                    "partner_bank_municipality": highlight(
                        p.bank_id_ref.city or ""
                    ),
                    "partner_bank_province": highlight(
                        p.bank_id_ref.state_id.name or ""
                    ),
                    "partner_appointed_by_agreement": highlight(
                        p.appointed_by_agreement
                    ),
                    "partner_appointment_date": fmt_date(p.appointment_date),
                }
            )
        elif contract_type == "tcp":
            template_vals.update(
                {
                    "id_card": highlight(p.id_card),
                    "partner_municipality": highlight(p.city),
                    "partner_province": highlight(p.state_id.name),
                    "partner_issued_by_location": highlight(p.issued_by),
                    "partner_bank_name_mlc": highlight(p.bank_id_ref.name),
                    "tcp_bank_mlc_branch": highlight(p.tcp_bank_mlc_branch),
                    "partner_bank_address_mlc": highlight(p.bank_id_ref.street),
                    "partner_bank_municipality_mlc": highlight(p.bank_id_ref.city),
                    "partner_bank_province_mlc": highlight(
                        p.bank_id_ref.state_id.name
                    ),
                    "partner_bank_name_cup": highlight(p.bank_id_ref.name),
                    "tcp_bank_cup_branch": highlight(p.tcp_bank_cup_branch),
                    "partner_bank_address_cup": highlight(p.bank_id_ref.street),
                    "partner_bank_municipality_cup": highlight(p.bank_id_ref.city),
                    "partner_bank_province_cup": highlight(
                        p.bank_id_ref.state_id.name
                    ),
                }
            )

        # Perform replacements
        for var_name, value in template_vals.items():
            if var_name == "partner_via" and not oeb:
                continue  # Skip so the regex below can find and remove it
            content = content.replace(f"{{{{{var_name}}}}}", value)

        # If OEB is empty, remove the phrase "a través de {{partner_via}}"
        if not oeb:
            content = re.sub(
                r"\s*a\s+trav[ée]s\s+de\s+(<strong[^>]*>)?\s*\{\{partner_via\}\}\s*(</strong>)?",
                "",
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                r"(<strong[^>]*>)?\s*\{\{partner_via\}\}\s*(</strong>)?",
                "",
                content,
            )

        content = content.strip()
        content = self.env["contrato.template"]._format_to_html(content)
        return content

    def action_generate_content(self):
        """Generate HTML content for the contract using the stored template."""
        for record in self:
            html = record._build_content_html()
            record.content = Markup(html)
            record.with_context(_generating_content=True).write(
                {"content_generated": True}
            )

    def action_generate_content_for_suplemento(self, suplemento):
        """Generate HTML content for a marco suplemento using its overriding field values."""
        self.ensure_one()
        overrides = {}
        for field_name in (
            "representative_id",
            "our_representative_id",
            "our_rep_decision_number",
            "our_rep_decision_date",
            "start_date",
            "validity_years",
        ):
            val = getattr(suplemento, field_name, None)
            if val:
                overrides[field_name] = val

        try:
            html = self._build_content_html(overrides)
        except UserError:
            return
        header = '<h3 style="text-align:center;">(Suplemento)</h3>\n'
        suplemento.with_context(_generating_content=True).write(
            {"content": Markup(header + html)}
        )

    def _create_suplemento_from_vals(self, vals: dict, changed_fields: frozenset):
        """Create a suplemento for this firmado marco with the proposed field changes."""
        self.ensure_one()
        changed_labels = [
            self._SUPLEMENTO_FIELD_LABELS[f]
            for f in changed_fields
            if f in self._SUPLEMENTO_FIELD_LABELS
        ]
        description = ", ".join(changed_labels)

        # Baseline: current marco values
        sup_vals = {
            "marco_id": self.id,
            "description": description,
            "representative_id": self.representative_id.id if self.representative_id else False,
            "our_representative_id": self.our_representative_id.id if self.our_representative_id else False,
            "authorized_contact_ids": [(6, 0, self.authorized_contact_ids.ids)],
            "our_rep_decision_number": self.our_rep_decision_number,
            "our_rep_decision_date": self.our_rep_decision_date,
            "start_date": self.start_date,
            "validity_years": self.validity_years,
        }

        # Apply the incoming changes (only tracked fields)
        for field in changed_fields:
            if field in vals:
                sup_vals[field] = vals[field]

        sup = self.env["contrato.suplemento"].create(sup_vals)

        # Auto-generate suplemento content
        try:
            self.action_generate_content_for_suplemento(sup)
        except Exception:
            pass

    def write(self, vals):
        tracked_in_vals = vals.keys() & self._SUPLEMENTO_TRACKED_FIELDS
        if tracked_in_vals and not self.env.su:
            firmado_records = self.filtered(lambda r: r.state == "firmado")
            if firmado_records:
                for record in firmado_records:
                    record._create_suplemento_from_vals(vals, tracked_in_vals)
                non_firmado = self - firmado_records
                if non_firmado:
                    result = super(ContratoMarco, non_firmado).write(vals)
                    non_firmado._auto_regenerate_content(vals)
                return True

        result = super().write(vals)
        self._auto_regenerate_content(vals)
        return result

    def _auto_regenerate_content(self, vals: dict) -> None:
        """Regenerates contract content automatically when content-related fields change."""
        if self.env.context.get("_generating_content"):
            return
        if not self._CONTENT_FIELDS & vals.keys():
            return
        for record in self.filtered(
            lambda r: r.content_generated and r.state not in ("firmado", "cancelado")
        ):
            try:
                record.with_context(_generating_content=True).action_generate_content()
            except UserError:
                pass
