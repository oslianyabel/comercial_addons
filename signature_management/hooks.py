import logging

_logger = logging.getLogger(__name__)

MODULE_NAME = "Signature Management (signature_management)"


def post_init_hook(env) -> None:
    """Notify the developer after the module is installed."""
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
