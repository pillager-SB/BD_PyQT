"""Логирование событий сервера"""

import sys
import os

sys.path.append('../')
import logging
from logging.handlers import TimedRotatingFileHandler
from common.variables import LOGGING_LEVEL, ENCODING

SERVER_FORMATTER = logging.Formatter("%(asctime)s %(levelname)s %(module)s %(message)s")  # Объект форматирования.

PATH = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(PATH, 'server.log')  # Файл для записи логов.

# Циклическое ежедневное логирование и переименование старых файлов в полночь по UTC.
FILE_HANDLER = TimedRotatingFileHandler(PATH,
                                        when='midnight',
                                        interval=1,
                                        backupCount=3,
                                        encoding=ENCODING,
                                        utc=True)
FILE_HANDLER.setFormatter(SERVER_FORMATTER)  # Подключение объекта форматирования к обработчику
FILE_HANDLER.setLevel(logging.DEBUG)  # Установка логирования от уровня "Предупреждения" и выше.

LOGGER = logging.getLogger('server')  # Экземпляр регистратора верхнего уровня.
LOGGER.addHandler(FILE_HANDLER)
LOGGER.setLevel(LOGGING_LEVEL)

if __name__ == '__main__':
    LOGGER.critical('Критическая ошибка')
    LOGGER.error('Ошибка')
    LOGGER.warning('Предупреждение')  # Сообщения с важностью ниже этой не должны попасть в server.log
    LOGGER.info('Информационное сообщение')
    LOGGER.debug('Отладочная информация')
