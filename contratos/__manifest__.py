{
    "name": "Master Contracts",
    "version": "17.0.1.0.17",
    "category": "Services",
    "summary": "Module for managing master contracts for MiPymes, TCP, and Companies",
    "description": """
        Permite la creación y gestión de contratos marcos, autocompletando la información desde los contactos.
    """,
    "author": "Osliani Figueiras Saucedo. Soluciones DTeam",
    "depends": ["base", "contacts", "partner_custom_fields"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/template_import_wizard_views.xml",
        "wizard/template_import_wizard_views.xml",
        "views/contrato_views.xml",
        "views/contrato_template_views.xml",
        "report/contrato_reports.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}