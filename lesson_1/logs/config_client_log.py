"""Логирование событий клиента"""

import sys
import os
sys.path.append('../')
import logging
from common.variables import LOGGING_LEVEL, ENCODING

# Объект форматирования.
client_formatter = logging.Formatter("%(asctime)s %(levelname)s %(filename)s %(message)s")


path = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(path, 'client.log')  # Файл для записи логов.

# Создаём потоки вывода логов.
steam = logging.StreamHandler(sys.stderr)
steam.setFormatter(client_formatter)
steam.setLevel(logging.INFO)
log_file = logging.FileHandler(path, encoding=ENCODING)
log_file.setFormatter(client_formatter)

# Создаём регистратор и настраиваем его.
logger = logging.getLogger('client')
logger.addHandler(steam)
logger.addHandler(log_file)
logger.setLevel(LOGGING_LEVEL)

if __name__ == '__main__':
    logger.critical('Тест: Критическая ошибка')
    logger.error('Тест: Ошибка')
    logger.warning('Тест: Предупреждение')
    logger.info('Тест: Информационное сообщение')
    logger.debug('Тест: Отладочная информация')
