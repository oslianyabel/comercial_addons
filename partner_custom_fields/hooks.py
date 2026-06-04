import logging

_logger = logging.getLogger(__name__)

MODULE_NAME = "Partner Custom Fields (partner_custom_fields)"


def post_init_hook(env) -> None:
    """Migra compañías desde Excel y notifica al desarrollador."""
    # Migración de compañías clientes
    try:
        from odoo.addons.partner_custom_fields.migration import migrate_companies
        migrate_companies.run(env)
    except Exception as exc:
        _logger.warning(
            "post_init_hook: error durante la migración de compañías – %s", exc
        )

    # Notificación Telegram
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
