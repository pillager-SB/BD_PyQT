import json
import threading
import time
import socket
import hashlib
import hmac
import binascii
from PyQt5.QtCore import pyqtSignal, QObject

from common.variables import *
from common.utils import *
from common.errors import ServerError

logger = logging.getLogger('client')
# Объект блокировки сокета и работы с базой данных
socket_lock = threading.Lock()


# Класс-Transport, отвечает за взаимодействие с сервером.
class ClientTransport(threading.Thread, QObject):
    """
    Класс реализующий транспортную подсистему клиентского
    модуля. Отвечает за взаимодействие с сервером.
    """
    # Сигналы:
    new_message = pyqtSignal(dict)  # Новое сообщение.
    connection_lost = pyqtSignal()  # Потеря соединения.
    message_205 = pyqtSignal()  # Добавление / удаление клиента.

    def __init__(self, port, ip_address, database, username, passwd, keys):
        # Вызываем конструкторы предков
        threading.Thread.__init__(self)
        QObject.__init__(self)

        # Класс База данных - работа с базой
        self.database = database
        # Имя пользователя
        self.username = username
        # Пароль
        self.password = passwd
        # Сокет для работы с сервером
        self.transport = None
        # Набор ключей для шифрования
        self.keys = keys
        # Устанавливаем соединение:
        self.connection_init(port, ip_address)
        # Обновляю таблицы известных пользователей и контактов.
        try:
            self.user_list_update()
            self.contacts_list_update()
        except OSError as err:
            if err.errno:
                logger.critical(f'Потеряно соединение с сервером. Ошибка: {err}')
                raise ServerError('Потеряно соединение с сервером!')
            logger.error('Timeout соединения при обновлении списков пользователей.')
        except json.JSONDecodeError as err:
            logger.critical(f'Потеряно соединение с сервером.Ошибка: {err}')
            raise ServerError('Потеряно соединение с сервером!')
        # Флаг продолжения работы транспорта.
        self.running = True

    def connection_init(self, ip, port):
        """
        Метод инициализирует соединение с сервером.
        """
        self.transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Таймаут 5 секунд, необходим для освобождения сокета.
        self.transport.settimeout(5)

        # Пытаюсь соединиться с сервером. Количество попыток ATTEMPTS = 5.
        connected = False
        for i in range(ATTEMPTS):
            logger.info(f'Попытка подключения к серверу № 0{i + 1}')
            try:
                self.transport.connect((ip, port))
            except (OSError, ConnectionRefusedError):
                ...
            else:
                connected = True
                logger.debug('Установлено соединение с сервером')
                break  # Если удачно - прерываю цикл.
            time.sleep(1)

        # Если соединится не удалось - поднимаю исключение.
        if not connected:
            logger.critical('Не удалось установить соединение с сервером.')
            raise ServerError('Не удалось установить соединение с сервером.')

        logger.debug('Запуск диалога авторизации.')
        # Запускаем процедуру авторизации.
        # Получаем хэш пароля.
        passwd_bytes = self.password.encode('utf-8')
        salt = self.username.lower().encode('utf-8')
        passwd_hash = hashlib.pbkdf2_hmac('sha512', passwd_bytes, salt, 10000)
        passwd_hash_string = binascii.hexlify(passwd_hash)

        logger.debug(f'Passwd hash ready: {passwd_hash_string}')

        # Получаем публичный ключ и декодируем его из байтов.
        pubkey = self.keys.publickey().export_key().decode('ascii')

        # Авторизуемся на сервере.
        with socket_lock:
            presense = {
                ACTION: PRESENCE,
                TIME: time.time(),
                USER: {
                    ACCOUNT_NAME: self.username,
                    PUBLIC_KEY: pubkey
                }
            }
            logger.debug(f"Presence message = {presense}")
            # Отправляем серверу приветственное сообщение.
            try:
                send_message(self.transport, presense)
                ans = get_message(self.transport)
                logger.debug(f'Server response = {ans}.')
                # Если сервер вернул ошибку, бросаем исключение.
                if RESPONSE in ans:
                    if ans[RESPONSE] == 400:
                        raise ServerError(ans[ERROR])
                    elif ans[RESPONSE] == 511:
                        # Если всё нормально, то продолжаем процедуру
                        # авторизации.
                        ans_data = ans[DATA]
                        hash = hmac.new(
                            passwd_hash_string, ans_data.encode('utf-8'), 'MD5')
                        digest = hash.digest()
                        my_ans = RESPONSE_511
                        my_ans[DATA] = binascii.b2a_base64(
                            digest).decode('ascii')
                        send_message(self.transport, my_ans)
                        self.process_server_ans(get_message(self.transport))
            except (OSError, json.JSONDecodeError) as err:
                logger.debug(f'Connection error.', exc_info=err)
                raise ServerError('Сбой соединения в процессе авторизации.')

    def process_server_ans(self, message):
        """
        Метод-обработчик сообщений поступающих с сервера.
        """
        logger.debug(f'Разбор сообщения от сервера: {message}')

        # Если это подтверждение чего-либо
        if RESPONSE in message:
            if message[RESPONSE] == 200:
                return
            elif message[RESPONSE] == 400:
                raise ServerError(f'{message[ERROR]}')
            elif message[RESPONSE] == 205:
                self.user_list_update()
                self.contacts_list_update()
                self.message_205.emit()
            else:
                logger.error(
                    f'Получен неизвестный код подтверждения {message[RESPONSE]}')

        # Если это сообщение от пользователя, то добавляем его в базу,
        # даём сигнал о новом сообщении.
        elif ACTION in message and message[ACTION] == MESSAGE and SENDER in message and DESTINATION in message \
                and MESSAGE_TEXT in message and message[DESTINATION] == self.username:
            logger.debug(
                f'Получено сообщение от пользователя {message[SENDER]}:{message[MESSAGE_TEXT]}')
            self.new_message.emit(message)

    def contacts_list_update(self):
        """
        Метод обновляющий контакт-лист с сервера.
        """
        self.database.contacts_clear()
        logger.debug(f'Запрос контакт-листа для пользователя {self.name}')
        req = {
            ACTION: GET_CONTACTS,
            TIME: time.time(),
            USER: self.username
        }
        logger.debug(f'Сформирован запрос {req}')
        with socket_lock:
            send_message(self.transport, req)
            ans = get_message(self.transport)
        logger.debug(f'Получен ответ {ans}')
        if RESPONSE in ans and ans[RESPONSE] == 202:
            for contact in ans[LIST_INFO]:
                self.database.add_contact(contact)
        else:
            logger.error('Не удалось обновить список контактов.')

    def user_list_update(self):
        """
        Метод для обновления таблицы известных пользователей.
        """
        logger.debug(f'Запрос списка известных пользователей {self.username}')
        req = {
            ACTION: USERS_REQUEST,
            TIME: time.time(),
            ACCOUNT_NAME: self.username
        }
        with socket_lock:
            send_message(self.transport, req)
            ans = get_message(self.transport)
        if RESPONSE in ans and ans[RESPONSE] == 202:
            self.database.add_users(ans[LIST_INFO])
        else:
            logger.error('Не удалось обновить список известных пользователей.')

    def key_request(self, user):
        """
        Метод запрашивающий с сервера публичный ключ пользователя.
        """
        logger.debug(f'Запрос публичного ключа для {user}')
        req = {
            ACTION: PUBLIC_KEY_REQUEST,
            TIME: time.time(),
            ACCOUNT_NAME: user
        }
        with socket_lock:
            send_message(self.transport, req)
            ans = get_message(self.transport)
        if RESPONSE in ans and ans[RESPONSE] == 511:
            return ans[DATA]
        else:
            logger.error(f'Не удалось получить ключ собеседника{user}.')

    def add_contact(self, contact):
        """
        Метод отправляющий на сервер сведения о добавлении контакта.
        """
        logger.debug(f'Создание контакта {contact}')
        req = {
            ACTION: ADD_CONTACT,
            TIME: time.time(),
            USER: self.username,
            ACCOUNT_NAME: contact
        }
        with socket_lock:
            send_message(self.transport, req)
            self.process_server_ans(get_message(self.transport))

    def remove_contact(self, contact):
        """
        Метод отправляющий на сервер сведения об удалении контакта.
        """
        logger.debug(f'Удаление контакта {contact}')
        req = {
            ACTION: REMOVE_CONTACT,
            TIME: time.time(),
            USER: self.username,
            ACCOUNT_NAME: contact
        }
        with socket_lock:
            send_message(self.transport, req)
            self.process_server_ans(get_message(self.transport))

    def transport_shutdown(self):
        """
        Метод уведомляющий сервер о завершении работы клиента.
        """
        # Сброс флага работы транспорта.
        self.running = False
        message = {
            ACTION: EXIT,
            TIME: time.time(),
            ACCOUNT_NAME: self.username
        }
        with socket_lock:
            try:
                send_message(self.transport, message)
            except OSError:
                pass
        logger.debug('Транспорт завершает работу.')
        time.sleep(0.5)

    def send_message(self, to, message):
        """
        Метод отправляющий на сервер сообщения для пользователя.
        """
        message_dict = {
            ACTION: MESSAGE,
            SENDER: self.username,
            DESTINATION: to,
            TIME: time.time(),
            MESSAGE_TEXT: message
        }
        logger.debug(f'Сформирован словарь сообщения: {message_dict}')

        # Необходимо дождаться освобождения сокета для отправки сообщения.
        with socket_lock:
            send_message(self.transport, message_dict)
            self.process_server_ans(get_message(self.transport))
            logger.info(f'Отправлено сообщение для пользователя {to}')

    def run(self):
        """
        Метод содержащий основной цикл работы транспортного потока.
        """
        logger.debug('Запущен процесс - приёмник сообщений с сервера.')
        while self.running:
            # Остановка на секунду, после попытка захватить сокет.
            time.sleep(1)
            message = None
            with socket_lock:
                try:
                    self.transport.settimeout(0.5)
                    message = get_message(self.transport)
                except OSError as err:
                    if err.errno:
                        logger.critical(f'Потеряно соединение с сервером.')
                        self.running = False
                        self.connection_lost.emit()
                # Проблемы с соединением
                except (
                        ConnectionError, ConnectionAbortedError, ConnectionResetError,
                        json.JSONDecodeError, TypeError):
                    logger.debug(f'Потеряно соединение с сервером.')
                    self.running = False
                    self.connection_lost.emit()
                # Если сообщение получено, то вызываем функцию обработчик:
                if message:
                    logger.debug(f'Принято сообщение с сервера: {message}')
                    self.process_server_ans(message)
