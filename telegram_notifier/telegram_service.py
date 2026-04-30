import logging
from pathlib import Path

import requests
from dotenv import dotenv_values

_logger = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).parent.parent / ".env"
_config = dotenv_values(_ENV_PATH)

BOT_TOKEN: str = _config.get("TELEGRAM_BOT_TOKEN_NOTIFIER", "")
CHAT_ID: str = _config.get("TELEGRAM_DEV_CHAT_ID", "")

_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_MESSAGE_LENGTH = 4096


def send_message(text: str) -> None:
    """Send a plain-text message to the developer's Telegram chat.

    Silently logs a warning if credentials are missing or the request fails,
    so that a notification error never disrupts normal Odoo operation.
    """
    if not BOT_TOKEN or not CHAT_ID:
        _logger.warning("Telegram notifier: BOT_TOKEN or CHAT_ID not configured.")
        return

    # Truncate to Telegram's limit
    if len(text) > _MAX_MESSAGE_LENGTH:
        text = text[: _MAX_MESSAGE_LENGTH - 100] + "\n\n[... mensaje truncado ...]"

    try:
        response = requests.post(
            _TELEGRAM_API_URL.format(token=BOT_TOKEN),
            json={"chat_id": CHAT_ID, "text": text},
            timeout=10,
        )
        if not response.ok:
            _logger.warning(
                "Telegram notifier: API error %s – %s",
                response.status_code,
                response.text,
            )
    except requests.RequestException as exc:
        _logger.warning("Telegram notifier: could not send message – %s", exc)


class TelegramErrorHandler(logging.Handler):
    """Logging handler that forwards ERROR/CRITICAL records from extra_addons
    modules to the developer via Telegram."""

    # Prefixes of logger names that should be forwarded
    _WATCHED_PREFIXES = (
        "odoo.addons.contratos",
        "odoo.addons.contratos_especificos",
        "odoo.addons.partner_custom_fields",
        "odoo.addons.signature_management",
        "odoo.addons.telegram_notifier",
    )

    def emit(self, record: logging.LogRecord) -> None:
        if not any(record.name.startswith(p) for p in self._WATCHED_PREFIXES):
            return

        try:
            module_label = record.name
            level = record.levelname
            message = self.format(record)
            text = (
                f"🚨 *Error en módulo Odoo*\n"
                f"📦 Módulo: {module_label}\n"
                f"⚠️ Nivel: {level}\n\n"
                f"{message}"
            )
            send_message(text)
        except Exception:  # noqa: BLE001
            # Never let the notification handler raise an exception
            pass


def _register_handler() -> None:
    """Attach the Telegram error handler to the root logger once."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, TelegramErrorHandler):
            return  # already registered
    handler = TelegramErrorHandler(level=logging.ERROR)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(name)s\n%(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
    )
    root_logger.addHandler(handler)
    _logger.info("Telegram error handler registered.")
