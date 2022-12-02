import logging
import sys

from common.variables import DEFAULT_PORT

# Инициализация логера.
# Метод определения модуля, источника запуска.
if sys.argv[0].find('client') == -1:
    # если не клиент, то сервер!
    logger = logging.getLogger('server')
else:
    # ну, раз не сервер, то клиент
    logger = logging.getLogger('client')


class PortValidator:
    def __set__(self, instance, value):
        if value < 1024 or value > 65535:
            logger.critical(
                f'Номер {value} не является приемлемым номером порта. '
                f'Допустимы номера в диапазоне 1024-65535.')
            raise TypeError('Некорректный номер порта')
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name):
        self.name = name
