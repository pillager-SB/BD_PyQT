"""Constants"""
import logging

# Порт по умолчанию для сетевого взаимодействия.
DEFAULT_PORT = 7777
# IP-адрес по умолчанию для подключения клиента.
DEFAULT_IP_ADDRESS = '127.0.0.1'
# Max размер очереди подключений.
MAX_CONNECTION = 5
# Max длина сообщения в байтах.
MAX_PACKAGE_LENGTH = 1024
# Используемая в проекте кодировка.
ENCODING = 'utf-8'
# Установка для верхнего уровня логирования.
LOGGING_LEVEL = logging.DEBUG


# Основные ключи протокола JIM.
ACTION = 'action'
TIME = 'time'
USER = 'user'
ACCOUNT_NAME = 'account_name'
SENDER = 'from'
DESTINATION = 'to'

# Прочие ключи используемые в протоколе.
PRESENCE = 'presence'
RESPONSE = 'response'
ERROR = 'error'
MESSAGE = 'message'
MESSAGE_TEXT = 'mess_text'
EXIT = 'exit'
HELP = f'Список поддерживаемых команд:\n' \
       f'-m, message - отправить сообщение. Для кого и текст сообщения - ввод в строке.\n' \
       f'-h, -?, help - вывести подсказки по командам.\n' \
       f'-e, exit - выход из программы.'
SERVER_HELP = f'Список поддерживаемых команд:\n' \
              f'users - список известных пользователей.\n' \
              f'connected - список подключенных пользователей.\n' \
              f'loghist - история входов пользователя.\n' \
              f'exit - завершение работы сервера.\n' \
              f'help - вывод справки по поддерживаемым командам.'
SERVER_HELP_LOGHIST = f'Введите имя пользователя для просмотра истории.\n' \
                      f'Для вывода всей истории, нажмите Enter.'
SERVER_DATABASE = 'sqlite:///server_base.db3'
