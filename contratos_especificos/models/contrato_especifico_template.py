import os
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContratoEspecificoTemplate(models.Model):
    _name = "contrato.especifico.template"
    _description = "Specific Contract Template"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    type = fields.Selection(
        [
            # ── Existentes ──────────────────────────────────────────────────
            ("cgm_disponibilidad", "CGM Disponibilidad y Soporte"),
            ("productos_soporte", "Productos Soporte"),
            ("soporte_desarrollo", "Servicio Soporte Desarrollo"),
            ("versat_iniciales", "Versat Servicios Iniciales"),
            # ── Versat ──────────────────────────────────────────────────────
            ("versat_soporte", "Versat Soporte"),
            ("versat_licencia", "Versat Licencia"),
            ("versat_licencia_activacion", "Versat Licencia y Activación"),
            ("versat_soporte_activacion", "Versat Soporte y Activación"),
            ("versat_lic_activ_sop_mipyme", "Versat Lic.+Activ.+Sop. MIPYME"),
            ("versat_lic_activ_sop_tcp", "Versat Lic.+Activ.+Sop. TCP"),
            ("versat_diagnostico", "Versat Diagnóstico"),
            # ── Productos genéricos ──────────────────────────────────────────
            ("productos_suscripcion_soporte", "Productos Suscripción y Soporte"),
            ("productos_servicios_iniciales", "Productos Servicios Iniciales"),
            ("productos_acompanamiento", "Productos Acompañamiento"),
            ("productos_proc_datos", "Productos Procesamiento de Datos"),
            # ── Segurmática ──────────────────────────────────────────────────
            ("segurmatica_licencia", "Segurmática Licencia"),
            ("segurmatica_licencia_soporte", "Segurmática Licencia y Soporte"),
            # ── Firma Digital ────────────────────────────────────────────────
            ("firma_digital", "Certificados y Servicios Firma Digital"),
            # ── Formación ───────────────────────────────────────────────────
            ("curso_juridicas", "Curso Formación - Personas Jurídicas"),
            ("curso_naturales", "Curso Formación - Personas Naturales"),
            # ── Servicios técnicos ───────────────────────────────────────────
            ("servicio_desarrollo", "Servicio Desarrollo de Software"),
            ("servicio_consultoria", "Servicio Consultoría"),
            ("servicio_psi", "Servicio Asesoramiento PSI"),
            ("servicio_iniciales_so", "Servicio Iniciales Sistema Operativo"),
            ("servicio_reparacion_bd", "Servicio Reparación Base de Datos"),
            ("servicio_log_correo", "Servicio Análisis Log de Correo"),
            ("servicio_log_internet", "Servicio Análisis Log de Internet"),
            ("servicio_vulnerabilidades", "Servicio Detección de Vulnerabilidades"),
            ("servicio_descontaminacion", "Servicio Descontaminación"),
            ("servicio_recuperacion", "Servicio Recuperación de Información"),
            ("servicio_externo_ti", "Servicio Externo de Operaciones TI"),
            ("servicio_redes", "Servicio Redes Informáticas"),
            ("servicio_redes_webmaster", "Servicio Redes Informáticas Webmaster"),
            ("servicio_webmaster", "Servicio Webmaster"),
            ("servicio_webmaster_hosting", "Servicio Webmaster y Hosting"),
            ("servicio_desarrollo_web", "Servicio Desarrollo Sitio Web"),
            # ── Especiales ───────────────────────────────────────────────────
            ("obligaciones_pendientes", "Contrato Obligaciones Pendientes"),
        ],
        string="Contract Type",
        required=True,
    )
    content = fields.Html(string="Template Content", required=True)
    active = fields.Boolean(string="Active", default=True)

    # Sync Tracking
    last_sync_date = fields.Datetime(string="Last Sync from Filesystem")
    sync_state = fields.Selection(
        [("synced", _("Synced")), ("modified", _("Modified"))],
        string="Sync Status",
        compute="_compute_sync_state",
        store=True,
    )

    available_variables = fields.Text(
        string="Available Variables",
        compute="_compute_available_variables",
        help="List of variables that you can use in this template.",
    )

    _sql_constraints = [
        (
            "type_unique",
            "UNIQUE(type)",
            "A template for this contract type already exists.",
        )
    ]

    # -------------------------------------------------------------------------
    # Template type -> filename mapping
    # -------------------------------------------------------------------------
    TEMPLATE_FILES = {
        # Existentes
        "cgm_disponibilidad": "CGM Disponibilidad y Soporte.txt",
        "productos_soporte": "Productos Soporte.txt",
        "soporte_desarrollo": "Servicio Soporte Desarrollo.txt",
        "versat_iniciales": "Versat Servicios Iniciales.txt",
        # Versat
        "versat_soporte": "Versat Soporte.txt",
        "versat_licencia": "Versat Licencia.txt",
        "versat_licencia_activacion": "Versat Licencia y Activacion.txt",
        "versat_soporte_activacion": "Versat Soporte y Activacion.txt",
        "versat_lic_activ_sop_mipyme": "Versat Lic Activ Sop MIPYME.txt",
        "versat_lic_activ_sop_tcp": "Versat Lic Activ Sop TCP.txt",
        "versat_diagnostico": "Versat Diagnostico.txt",
        # Productos genéricos
        "productos_suscripcion_soporte": "Productos Suscripcion y Soporte.txt",
        "productos_servicios_iniciales": "Productos Servicios Iniciales.txt",
        "productos_acompanamiento": "Productos Acompanamiento.txt",
        "productos_proc_datos": "Productos Procesamiento de Datos.txt",
        # Segurmática
        "segurmatica_licencia": "Segurmatica Licencia.txt",
        "segurmatica_licencia_soporte": "Segurmatica Licencia y Soporte.txt",
        # Firma Digital
        "firma_digital": "Firma Digital.txt",
        # Formación
        "curso_juridicas": "Curso Formacion Juridicas.txt",
        "curso_naturales": "Curso Formacion Naturales.txt",
        # Servicios técnicos
        "servicio_desarrollo": "Servicio Desarrollo.txt",
        "servicio_consultoria": "Servicio Consultoria.txt",
        "servicio_psi": "Servicio Asesoramiento PSI.txt",
        "servicio_iniciales_so": "Servicio Iniciales SO.txt",
        "servicio_reparacion_bd": "Servicio Reparacion Base Datos.txt",
        "servicio_log_correo": "Servicio Analisis Log Correo.txt",
        "servicio_log_internet": "Servicio Analisis Log Internet.txt",
        "servicio_vulnerabilidades": "Servicio Deteccion Vulnerabilidades.txt",
        "servicio_descontaminacion": "Servicio Descontaminacion.txt",
        "servicio_recuperacion": "Servicio Recuperacion Informacion.txt",
        "servicio_externo_ti": "Servicio Externo TI.txt",
        "servicio_redes": "Servicio Redes Informaticas.txt",
        "servicio_redes_webmaster": "Servicio Redes Webmaster.txt",
        "servicio_webmaster": "Servicio Webmaster.txt",
        "servicio_webmaster_hosting": "Servicio Webmaster y Hosting.txt",
        "servicio_desarrollo_web": "Servicio Desarrollo Sitio Web.txt",
        # Especiales
        "obligaciones_pendientes": "Obligaciones Pendientes.txt",
    }

    # -------------------------------------------------------------------------
    # Variables
    # -------------------------------------------------------------------------
    COMMON_VARIABLES = [
        "specific_number",
        "marco_number",
        "marco_date",
        "partner_name",
        "partner_via",
        "partner_short_name",
        "start_date",
        "validity_years",
        "day",
        "month",
        "year",
        # Leaders (present in most templates)
        "our_project_leader",
        "project_leader",
    ]

    # Types that use {{our_representative}}, {{our_rep_function}}, {{our_rep_decision_number}}
    _TYPES_WITH_REPRESENTATIVE = frozenset(
        [
            "cgm_disponibilidad",
            "productos_soporte",
            "productos_suscripcion_soporte",
            "curso_naturales",
        ]
    )

    # Types that use {{application_name}}
    _TYPES_WITH_APP_NAME = frozenset(
        [
            "productos_soporte",
            "soporte_desarrollo",
            "productos_suscripcion_soporte",
            "productos_servicios_iniciales",
            "productos_acompanamiento",
            "productos_proc_datos",
            "servicio_externo_ti",
        ]
    )

    # Types that use {{project_leader}} and/or {{our_project_leader}}
    _TYPES_WITH_LEADERS = frozenset(
        [
            "versat_iniciales",
            "versat_diagnostico",
            "productos_servicios_iniciales",
            "productos_acompanamiento",
            "productos_proc_datos",
            "servicio_desarrollo",
            "servicio_consultoria",
            "servicio_psi",
            "servicio_iniciales_so",
            "servicio_reparacion_bd",
            "servicio_log_correo",
            "servicio_log_internet",
            "servicio_vulnerabilidades",
            "servicio_descontaminacion",
            "servicio_recuperacion",
            "servicio_externo_ti",
            "servicio_redes",
            "servicio_redes_webmaster",
            "servicio_webmaster",
            "servicio_webmaster_hosting",
            "servicio_desarrollo_web",
        ]
    )

    TYPE_EXTRA_VARIABLES = {
        "cgm_disponibilidad": [
            "our_representative",
            "our_rep_function",
            "our_rep_decision_number",
        ],
        "productos_soporte": [
            "our_representative",
            "our_rep_function",
            "our_rep_decision_number",
            "application_name",
        ],
        "soporte_desarrollo": [
            "application_name",
        ],
        "versat_iniciales": [],
        # New types
        "versat_soporte": [],
        "versat_licencia": [],
        "versat_licencia_activacion": [],
        "versat_soporte_activacion": [],
        "versat_lic_activ_sop_mipyme": [],
        "versat_lic_activ_sop_tcp": [],
        "versat_diagnostico": [],
        "productos_suscripcion_soporte": [
            "our_representative",
            "our_rep_function",
            "our_rep_decision_number",
            "application_name",
        ],
        "productos_servicios_iniciales": ["application_name"],
        "productos_acompanamiento": ["application_name"],
        "productos_proc_datos": ["application_name"],
        "segurmatica_licencia": [],
        "segurmatica_licencia_soporte": [],
        "firma_digital": [],
        "curso_juridicas": [],
        "curso_naturales": [
            "our_representative",
            "our_rep_function",
            "our_rep_decision_number",
        ],
        "servicio_desarrollo": [],
        "servicio_consultoria": [],
        "servicio_psi": [],
        "servicio_iniciales_so": [],
        "servicio_reparacion_bd": [],
        "servicio_log_correo": [],
        "servicio_log_internet": [],
        "servicio_vulnerabilidades": [],
        "servicio_descontaminacion": [],
        "servicio_recuperacion": [],
        "servicio_externo_ti": ["application_name"],
        "servicio_redes": [],
        "servicio_redes_webmaster": [],
        "servicio_webmaster": [],
        "servicio_webmaster_hosting": [],
        "servicio_desarrollo_web": [],
        "obligaciones_pendientes": [],
    }

    COMMON_REQUIRED = [
        "specific_number",
        "marco_number",
        "marco_date",
        "partner_name",
        "partner_short_name",
        "day",
        "month",
        "year",
    ]

    TYPE_REQUIRED_EXTRA = {
        "cgm_disponibilidad": [
            "our_representative",
            "our_rep_function",
            "our_rep_decision_number",
        ],
        "productos_soporte": [
            "our_representative",
            "our_rep_function",
            "our_rep_decision_number",
        ],
        "soporte_desarrollo": [],
        "versat_iniciales": ["project_leader"],
        # New types
        "versat_soporte": [],
        "versat_licencia": [],
        "versat_licencia_activacion": [],
        "versat_soporte_activacion": [],
        "versat_lic_activ_sop_mipyme": [],
        "versat_lic_activ_sop_tcp": [],
        "versat_diagnostico": ["project_leader"],
        "productos_suscripcion_soporte": [
            "our_representative",
            "our_rep_function",
            "our_rep_decision_number",
        ],
        "productos_servicios_iniciales": ["project_leader"],
        "productos_acompanamiento": ["project_leader"],
        "productos_proc_datos": ["project_leader"],
        "segurmatica_licencia": [],
        "segurmatica_licencia_soporte": [],
        "firma_digital": [],
        "curso_juridicas": [],
        "curso_naturales": [
            "our_representative",
            "our_rep_function",
            "our_rep_decision_number",
        ],
        "servicio_desarrollo": ["project_leader"],
        "servicio_consultoria": ["project_leader"],
        "servicio_psi": ["project_leader"],
        "servicio_iniciales_so": ["project_leader"],
        "servicio_reparacion_bd": ["project_leader"],
        "servicio_log_correo": ["project_leader"],
        "servicio_log_internet": ["project_leader"],
        "servicio_vulnerabilidades": ["project_leader"],
        "servicio_descontaminacion": ["project_leader"],
        "servicio_recuperacion": ["project_leader"],
        "servicio_externo_ti": ["project_leader"],
        "servicio_redes": ["project_leader"],
        "servicio_redes_webmaster": [],
        "servicio_webmaster": [],
        "servicio_webmaster_hosting": [],
        "servicio_desarrollo_web": [],
        "obligaciones_pendientes": [],
    }

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------
    def _compute_available_variables(self):
        for record in self:
            vars_list = self.COMMON_VARIABLES.copy()
            extra = self.TYPE_EXTRA_VARIABLES.get(record.type, [])
            vars_list += extra
            record.available_variables = "\n".join(["{{" + v + "}}" for v in vars_list])

    @api.depends("content", "last_sync_date")
    def _compute_sync_state(self):
        for record in self:
            fs_content = record._get_filesystem_content()
            if fs_content and self._prepare_for_comparison(
                record.content
            ) == self._prepare_for_comparison(fs_content):
                record.sync_state = "synced"
            else:
                record.sync_state = "modified"

    # -------------------------------------------------------------------------
    # Filesystem sync
    # -------------------------------------------------------------------------
    def _get_base_path(self):
        """Detect the context/contratos especificos directory."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        extra_addons_path = os.path.abspath(os.path.join(current_dir, "..", ".."))
        return os.path.join(extra_addons_path, "context", "contratos especificos")

    def _get_filesystem_content(self):
        """Get and format the current filesystem content for comparison."""
        base_path = self._get_base_path()
        filename = self.TEMPLATE_FILES.get(self.type)
        if filename:
            template_path = os.path.join(base_path, filename)
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    raw_content = f.read()
                    return self._format_to_html(raw_content)
        return False

    def _prepare_for_comparison(self, html):
        """Standardize HTML for comparison."""
        if not html:
            return ""
        res = re.sub(r"<(\w+)[^>]*>", r"<\1>", html)
        res = res.lower()
        res = re.sub(r"\s+", "", res)
        res = res.replace("&nbsp;", "")
        return res

    @api.model
    def _format_to_html(self, raw_content):
        """Convert plain text contract to Odoo-friendly HTML."""
        if not raw_content:
            return ""

        has_block_tags = re.search(
            r"<(p|div|h1|h2|h3|table|br|ul|ol|li)", raw_content, re.IGNORECASE
        )

        if not has_block_tags:
            lineas = raw_content.splitlines()
            formatted_lineas = []
            for idx, linea in enumerate(lineas):
                linea = linea.strip()
                if not linea:
                    continue

                is_header = len(linea) < 120 and (linea.isupper() or idx == 0)

                if is_header:
                    font_size = "18px" if idx == 0 else "16px"
                    formatted_lineas.append(
                        '<h2 style="text-align: center; font-weight: bold;'
                        " font-size: " + font_size + "; margin: 0; "
                        'padding-top: 10px; padding-bottom: 5px;">' + linea + "</h2>"
                    )
                else:
                    formatted_lineas.append(
                        '<p style="text-align: justify; margin: 0;'
                        ' line-height: 1.2;">' + linea + "</p>"
                    )
            raw_content = "".join(formatted_lineas)

        # Bold variables {{variable}}
        raw_content = re.sub(
            r"\{\{([^{}]+)\}\}", r"<strong>{{\1}}</strong>", raw_content
        )

        return raw_content

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    @api.model
    def _get_required_variables(self, template_type):
        """Return list of variables that MUST be present in the template."""
        required = self.COMMON_REQUIRED.copy()
        extra = self.TYPE_REQUIRED_EXTRA.get(template_type, [])
        required += extra
        return required

    def _validate_content_variables(self, content, template_type):
        """Check if all required variables are present in the content."""
        if not content:
            return
        required = self._get_required_variables(template_type)
        missing = []
        for var in required:
            pattern = r"\{\{\s*%s\s*\}\}" % re.escape(var)
            if not re.search(pattern, content):
                missing.append("{{" + var + "}}")

        if missing:
            raise UserError(
                _(
                    "The template content is missing the following required "
                    "variables: %s. These are necessary for correct contract "
                    "generation."
                )
                % ", ".join(missing)
            )

    def write(self, vals):
        """Validate variables if content is updated."""
        if "content" in vals:
            for record in self:
                self._validate_content_variables(
                    vals["content"], vals.get("type", record.type)
                )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Validate variables on creation."""
        for vals in vals_list:
            if "content" in vals and "type" in vals:
                self._validate_content_variables(vals["content"], vals["type"])
        return super().create(vals_list)

    def unlink(self):
        """Protect the last remaining template of each type."""
        for record in self:
            others = self.search([("type", "=", record.type), ("id", "!=", record.id)])
            if not others:
                raise UserError(
                    _("You cannot delete the last template for %s. It is required.")
                    % dict(self._fields["type"].selection).get(record.type)
                )
        return super().unlink()

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_open_import_wizard(self):
        """Open the import TXT wizard for this template."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Import TXT"),
            "res_model": "contrato.especifico.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_template_id": self.id},
        }

    def action_import_from_filesystem(self):
        """Import/overwrite all specific contract templates from filesystem."""
        base_path = self._get_base_path()
        count = 0
        now = fields.Datetime.now()

        for c_type, filename in self.TEMPLATE_FILES.items():
            template_path = os.path.join(base_path, filename)
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    raw_content = f.read()
                    if raw_content:
                        self._validate_content_variables(raw_content, c_type)
                        html_content = self._format_to_html(raw_content)
                        existing = self.search([("type", "=", c_type)], limit=1)
                        if existing:
                            existing.write(
                                {
                                    "content": html_content,
                                    "last_sync_date": now,
                                }
                            )
                        else:
                            self.create(
                                {
                                    "name": filename.replace(".txt", ""),
                                    "type": c_type,
                                    "content": html_content,
                                    "last_sync_date": now,
                                }
                            )
                        count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import Finished"),
                "message": _("Processed %s templates.") % count,
                "sticky": False,
            },
        }

    def action_reset_from_filesystem(self):
        """Force overwrite this template with the filesystem content."""
        base_path = self._get_base_path()
        filename = self.TEMPLATE_FILES.get(self.type)
        if filename:
            template_path = os.path.join(base_path, filename)
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    raw_content = f.read()
                    if raw_content:
                        self._validate_content_variables(raw_content, self.type)
                        self.write(
                            {
                                "content": self._format_to_html(raw_content),
                                "last_sync_date": fields.Datetime.now(),
                            }
                        )
                        return {
                            "type": "ir.actions.client",
                            "tag": "display_notification",
                            "params": {
                                "title": _("Template Reset"),
                                "message": _("Template restored from filesystem."),
                                "sticky": False,
                                "next": {
                                    "type": "ir.actions.client",
                                    "tag": "reload",
                                },
                            },
                        }
        return False
