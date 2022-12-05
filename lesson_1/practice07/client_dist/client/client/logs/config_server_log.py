"""Логирование событий сервера"""

import sys
import os

sys.path.append('../')
import logging
from logging.handlers import TimedRotatingFileHandler
from common.variables import LOGGING_LEVEL, ENCODING

# Создаём формировщик логов (formatter):
server_formatter = logging.Formatter("%(asctime)s %(levelname)s %(module)s %(message)s")  # Объект форматирования.

# Подготовка имени файла для логирования
path = os.getcwd()
path = os.path.join(path, 'server.log')  # Файл для записи логов.
# Создаём потоки вывода логов.
steam = logging.StreamHandler(sys.stderr)
steam.setFormatter(server_formatter)
steam.setLevel(logging.INFO)
# Циклическое ежедневное логирование и переименование старых файлов в полночь по UTC.
log_file = TimedRotatingFileHandler(path,
                                    when='midnight',
                                    interval=1,
                                    backupCount=3,
                                    encoding=ENCODING,
                                    utc=True)
log_file.setFormatter(server_formatter)

# создаём регистратор и настраиваем его
logger = logging.getLogger('server')
logger.addHandler(steam)
logger.addHandler(log_file)
logger.setLevel(LOGGING_LEVEL)

if __name__ == '__main__':
    logger.critical('Тест: Критическая ошибка')
    logger.error('Тест: Ошибка')
    logger.warning('Тест: Предупреждение')  # Сообщения с важностью ниже этой не должны попасть в server.log
    logger.info('Тест: Информационное сообщение')
    logger.debug('Тест: Отладочная информация')
