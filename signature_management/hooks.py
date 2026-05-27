import logging

_logger = logging.getLogger(__name__)

MODULE_NAME = "Signature Management (signature_management)"


import logging

_logger = logging.getLogger(__name__)

MODULE_NAME = "Signature Management (signature_management)"


def post_init_hook(env) -> None:
    """Set default Mi Empresa and notify the developer after the module is installed."""
    for company in env["res.company"].search([]):
        if not company.mi_empresa_partner_id:
            dteam = env["res.partner"].search(
                [("name", "ilike", "Soluciones DTeam"), ("is_company", "=", True)],
                limit=1,
            )
            if dteam:
                company.mi_empresa_partner_id = dteam
    try:
        from odoo.addons.telegram_notifier import send_message

        send_message(f"✅ Módulo instalado en Odoo\n📦 {MODULE_NAME}")
    except Exception as exc:
        _logger.warning(
            "post_init_hook: could not send Telegram notification – %s", exc
        )


def uninstall_hook(env) -> None:
    """Notify the developer before the module is uninstalled."""
    try:
        from odoo.addons.telegram_notifier import send_message

        send_message(f"🗑️ Módulo desinstalado de Odoo\n📦 {MODULE_NAME}")
    except Exception as exc:
        _logger.warning(
            "uninstall_hook: could not send Telegram notification – %s", exc
        )
