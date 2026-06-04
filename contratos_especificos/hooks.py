import logging
import os

_logger = logging.getLogger(__name__)

MODULE_NAME = "Specific Contracts (contratos_especificos)"


def _ensure_plantillas_dir() -> str:
    """Create and return the plantillas directory for the contratos_especificos module."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(current_dir, "static", "plantillas")
    os.makedirs(path, exist_ok=True)
    _logger.info("contratos_especificos: plantillas directory ready at %s", path)
    return path


def post_init_hook(env) -> None:
    """Crea directorio de plantillas, migra servicios y notifica al desarrollador."""
    # Crear directorio de plantillas
    _ensure_plantillas_dir()

    # Migración de servicios (productos de facturación)
    try:
        from odoo.addons.contratos_especificos.migration import migrate_services
        migrate_services.run(env)
    except Exception as exc:
        _logger.warning(
            "post_init_hook: error durante la migración de servicios – %s", exc
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
