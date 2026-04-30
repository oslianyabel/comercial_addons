{
    "name": "Partner Custom Fields",
    "version": "17.0.1.8.0",
    "category": "Base",
    "summary": "Add custom fields to partners and companies",
    "description": """
        Adds classification and ministry fields to the partner form view.
    """,
    "author": "Osliani Figueiras Saucedo",
    "depends": ["base", "contacts", "telegram_notifier"],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/res_company_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
