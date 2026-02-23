{
    "name": "Partner Custom Fields",
    "version": "17.0.1.7.1",
    "category": "Base",
    "summary": "Add custom fields to partners and companies",
    "description": """
        Adds classification and ministry fields to the partner form view.
    """,
    "author": "Antigravity",
    "depends": ["base", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
