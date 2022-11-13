"""Логирование событий клиента"""

import sys
import os

sys.path.append('../')
import logging
from common.variables import LOGGING_LEVEL, ENCODING

CLIENT_FORMATTER = logging.Formatter("%(asctime)s %(levelname)s %(module)s %(message)s")  # Объект форматирования.

PATH = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(PATH, 'client.log')  # Файл для записи логов.

FILE_HANDLER = logging.FileHandler(PATH, encoding=ENCODING)  # Обработчик для записи сообщений в файл.
FILE_HANDLER.setFormatter(CLIENT_FORMATTER)  # Подключение объекта форматирования к обработчику
FILE_HANDLER.setLevel(logging.DEBUG)  # Установка логирования от уровня "Предупреждения" и выше.

LOGGER = logging.getLogger('client')  # Экземпляр регистратора верхнего уровня.
LOGGER.addHandler(FILE_HANDLER)
LOGGER.setLevel(LOGGING_LEVEL)

if __name__ == '__main__':
    LOGGER.critical('Критическая ошибка')
    LOGGER.error('Ошибка')
    LOGGER.warning('Предупреждение')
    LOGGER.info('Информационное сообщение')
    LOGGER.debug('Отладочная информация')
