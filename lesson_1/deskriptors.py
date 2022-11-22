import logging
import sys

from common.variables import DEFAULT_PORT

SERVER_LOGGER = logging.getLogger('server')


class PortValidator:
    def __set__(self, instance, value):
        if value < 1024 or value > 65535:
            SERVER_LOGGER.critical(
                f'Номер {value} не является приемлемым номером порта. '
                f'Допустимы номера в диапазоне 1024-65535.')
            # Принудительное подключение 7777 порта (прописан в DEFAULT_PORT).
            value = DEFAULT_PORT
            # sys.exit(1)
        # Если номер порта валиден, добавляю его в список атрибутов объекта.
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name):
        self.name = name
