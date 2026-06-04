import logging
import os

_logger = logging.getLogger(__name__)

MODULE_NAME = "Master Contracts (contratos)"


def _ensure_plantillas_dir() -> str:
    """Create and return the plantillas directory for the contratos module."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(current_dir, "static", "plantillas")
    os.makedirs(path, exist_ok=True)
    _logger.info("contratos: plantillas directory ready at %s", path)
    return path


def post_init_hook(env) -> None:
    """Create plantillas directory and notify the developer after installation."""
    _ensure_plantillas_dir()
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
