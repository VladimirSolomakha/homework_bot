class Error(Exception):
    """Базовый класс для других исключений."""

    pass


class YandexError(Error):
    """Вызывается при ошибках practicum.yandex."""

    pass


class TelegramError(Error):
    """Вызывается при оибках Telegram."""

    pass


class YandexTypeError(TypeError):
    """Вызывается при ошибках practicum.yandex."""

    pass


class YandexKeyError(KeyError):
    """Вызывается при ошибках practicum.yandex."""

    pass
