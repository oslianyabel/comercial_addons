{
    "name": "Specific Contracts",
    "version": "17.0.1.0.0",
    "category": "Services",
    "summary": "Specific contracts with service lines, invoicing integration, and custom reports",
    "description": "Allows creating and managing specific contracts that reference signed master contracts.",
    "author": "Osliani Figueiras Saucedo",
    "depends": ["base", "contacts", "account", "product", "uom", "contratos", "partner_custom_fields"],
    "data": [
        "security/ir.model.access.csv",
        "data/specific_template_data.xml",
        "views/contrato_especifico_import_wizard_views.xml",
        "views/contrato_especifico_template_views.xml",
        "views/contrato_especifico_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}