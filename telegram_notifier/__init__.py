from .telegram_service import _register_handler, send_message

_register_handler()

__all__ = ["send_message"]
