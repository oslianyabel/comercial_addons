import os
import re
from html import unescape

from markupsafe import Markup
from odoo import _, models
from odoo.exceptions import UserError


class ContratoMarco(models.Model):
    _inherit = "contrato.marco"

    def action_generate_content(self):
        """Override to support database-stored templates with filesystem fallback and auto-import."""
        for record in self:
            # 1. Try to get template from DB first
            template = self.env["contrato.template"].search(
                [("type", "=", record.contract_type)], limit=1
            )
            content = ""

            if template:
                # Get content from DB. We force it to a plain string to allow regex later.
                content = unescape(str(template.content or ""))
            else:
                # 2. Fallback to Filesystem logic
                template_name = ""
                if record.contract_type == "mipyme":
                    template_name = "contrato marco Mipyme"
                elif record.contract_type == "tcp":
                    template_name = "contrato marco TCP.txt"
                elif record.contract_type == "empresa":
                    template_name = "contrato marco empresas.txt"

                if template_name:
                    base_path = "c:\\Users\\lilia\\Desktop\\Projects\\Odoo\\instancias\\odoo17_comercial2\\extra_addons\\context\\"
                    template_path = os.path.join(base_path, template_name)
                    if os.path.exists(template_path):
                        with open(template_path, "r", encoding="utf-8") as f:
                            raw_content = f.read()

                            # Use the standardized formatting logic
                            content = self.env["contrato.template"]._format_to_html(
                                raw_content
                            )

                            # Auto-import to DB
                            existing = self.env["contrato.template"].search(
                                [("type", "=", record.contract_type)], limit=1
                            )
                            if not existing:
                                self.env["contrato.template"].create(
                                    {
                                        "name": template_name.replace(
                                            ".txt", ""
                                        ).capitalize(),
                                        "type": record.contract_type,
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
            p = record.partner_id
            r = record.representative_id or p.represented_by_id
            our_r = record.our_representative_id

            comp = (
                record.env["res.company"].search(
                    [("name", "ilike", "Soluciones DTeam")], limit=1
                )
                or record.env.company
            )
            comp_partner = comp.partner_id

            # Validation
            missing = []
            if not record.our_representative_id:
                missing.append("Our Representative")
            if not record.our_rep_decision_number:
                missing.append("Our Rep. Decision Number")
            if not record.our_rep_decision_date:
                missing.append("Our Rep. Decision Date")
            if not r:
                missing.append("Customer Representative")

            req_p = [
                "tax_id",
                "reeup",
                "bank_account_cup",
                "phone",
                "email",
                "street",
                "city",
            ]
            if record.contract_type == "empresa":
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
            elif record.contract_type == "mipyme":
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
            elif record.contract_type == "tcp":
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
                    missing.append(f"Cliente: {p._fields[f].string}")
            if not comp_partner.titular:
                missing.append("Company: Bank Account Holder")

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

            # Building the universal variable dictionary
            vals = {
                "contract_number": highlight(record.name),
                "our_email": highlight(comp_partner.email),
                "our_representative": highlight(our_r.name),
                "our_rep_decision_number": highlight(record.our_rep_decision_number),
                "our_rep_decision_date": fmt_date(record.our_rep_decision_date),
                "partner_name": highlight(p.name),
                "partner_via": highlight(record.oeb) if record.oeb else "",
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
                "day": highlight(record.date.day),
                "month": highlight(record.date.strftime("%B")),
                "year": highlight(record.date.year),
            }

            if record.contract_type == "mipyme":
                vals.update(
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
            elif record.contract_type == "tcp":
                vals.update(
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
            for var_name, value in vals.items():
                if var_name == "partner_via" and not record.oeb:
                    continue  # Skip so the regex below can find and remove it
                content = content.replace(f"{{{{{var_name}}}}}", value)

            # If OEB is empty, remove the phrase "a través de {{partner_via}}"
            # including any surrounding <strong> HTML tags from the template
            if not record.oeb:
                content = re.sub(
                    r"\s*a\s+trav[ée]s\s+de\s+(<strong[^>]*>)?\s*\{\{partner_via\}\}\s*(</strong>)?",
                    "",
                    content,
                    flags=re.IGNORECASE,
                )
                # Also remove any remaining {{partner_via}} placeholder (with or without <strong>)
                content = re.sub(
                    r"(<strong[^>]*>)?\s*\{\{partner_via\}\}\s*(</strong>)?",
                    "",
                    content,
                )

            # --- FINAL FORMATTING PASS ---
            # We strip any dangling whitespaces and run it through the ultra-robust formatter
            content = content.strip()
            content = self.env["contrato.template"]._format_to_html(content)

            # Final assignment using Markup to tell Odoo this is safe HTML
            record.content = Markup(content)
