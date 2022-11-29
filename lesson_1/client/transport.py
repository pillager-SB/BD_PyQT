import argparse
import json
import sys
import os
import threading
import time
import socket
import logging
from PyQt5.QtCore import pyqtSignal, QObject

sys.path.append('../')
from common.variables import *
from common.utils import *
from common.errors import ServerError


CLIENT_LOGGER = logging.getLogger('client')
# Объект блокировки сокета и работы с базой данных
socket_lock = threading.Lock()


# Класс-Transport, отвечает за взаимодействие с сервером.
class ClientTransport(threading.Thread, QObject):
    # Сигналы:
    new_message = pyqtSignal(str)  # Новое сообщение.
    connection_lost = pyqtSignal()  # Потеря соединения.

    def __init__(self, port, ip_address, database, username):
        # Вызов конструкторов предков
        threading.Thread.__init__(self)
        QObject.__init__(self)

        # База данных.
        self.database = database
        # Имя пользователя.
        self.username = username
        # Сокет для работы с сервером.
        self.transport = None
        # Устанавливаем соединение:
        self.connection_init(ip_address, port)
        # Обновляю таблицы известных пользователей и контактов.
        try:
            self.user_list_update()
            self.contacts_list_request()
        except OSError as err:
            if err.errno:
                CLIENT_LOGGER.critical(f'Потеряно соединение с сервером. Ошибка: {err}')
                raise ServerError('Потеряно соединение с сервером!')
            CLIENT_LOGGER.error('Timeout соединения при обновлении списков пользователей.')
        except json.JSONDecodeError as err:
            CLIENT_LOGGER.critical(f'Потеряно соединение с сервером.Ошибка: {err}')
            raise ServerError('Потеряно соединение с сервером!')
        # Флаг продолжения работы транспорта.
        self.running = True

    def connection_init(self, ip, port):
        """
        Метод инициализирует соединение с сервером.
        :param port:
        :param ip:
        :return:
        """
        self.transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Таймаут 5 секунд, необходим для освобождения сокета.
        self.transport.settimeout(5)

        # Пытаюсь соединиться с сервером. Количество попыток ATTEMPTS = 5.
        connected = False
        for i in range(ATTEMPTS):
            CLIENT_LOGGER.info(f'Попытка подключения к серверу № 0{i + 1}')
            try:
                self.transport.connect((ip, port))
            except (OSError, ConnectionRefusedError):
                ...
            else:
                connected = True
                break  # Если удачно - прерываю цикл.
            time.sleep(1)

        # Если соединится не удалось - поднимаю исключение.
        if not connected:
            CLIENT_LOGGER.critical('Не удалось установить соединение с сервером')
            raise ServerError('Не удалось установить соединение с сервером')

        CLIENT_LOGGER.debug('Установлено соединение с сервером')

        # Посылаю серверу приветственное сообщение,
        # получаю ответ, что всё нормально или ловлю исключение.
        try:
            with socket_lock:
                send_message(self.transport, self.create_presence())
                self.process_server_ans(get_message(self.transport))
        except (OSError, json.JSONDecodeError):
            CLIENT_LOGGER.critical('Потеряно соединение с сервером!')
            raise ServerError('Потеряно соединение с сервером!')

        # Раз всё хорошо, сообщение об установке соединения.
        CLIENT_LOGGER.info('Соединение с сервером успешно установлено.')

    # Функция, генерирующая приветственное сообщение для сервера
    def create_presence(self):
        """
        Функция создает словарь-запрос о присутствии клиента.
        :return:
        """
        out = {
            ACTION: PRESENCE,
            TIME: time.time(),
            USER: {
                ACCOUNT_NAME: self.username
            }
        }
        CLIENT_LOGGER.debug(f'Сформировано {PRESENCE} сообщение для пользователя {self.username}')
        return out

    def process_server_ans(self, message):
        """
        Функция разбирающая ответы сервера
        :param message:
        :return: None
        """
        CLIENT_LOGGER.debug(f'Разбор ответа сервера: {message}')
        if RESPONSE in message:
            if message[RESPONSE] == 200:
                return
            elif message[RESPONSE] == 400:
                raise ServerError(f'400 : {message[ERROR]}')
            else:
                CLIENT_LOGGER.debug(f'Принят неизвестный код подтверждения {message[RESPONSE]}')

        # Если это сообщение от пользователя:
        # добавляем в базу, даём сигнал о новом сообщении.
        elif ACTION in message \
                and message[ACTION] == MESSAGE \
                and SENDER in message \
                and DESTINATION in message \
                and MESSAGE_TEXT in message \
                and message[DESTINATION] == self.username:
            CLIENT_LOGGER.debug(f'Получено сообщение от пользователя '
                                f'{message[SENDER]}:{message[MESSAGE_TEXT]}')
            self.database.save_message(message[SENDER], 'in', message[MESSAGE_TEXT])
            self.new_message.emit(message[SENDER])

    def contacts_list_request(self):
        """
        Функция обновляющая контакт-лист с сервера.
        :return:
        """
        CLIENT_LOGGER.debug(f'Запрос контакт-листа для пользователя {self.name}')
        req = {
            ACTION: GET_CONTACTS,
            TIME: time.time(),
            USER: self.username
        }
        CLIENT_LOGGER.debug(f'Сформирован запрос {req}')
        with socket_lock:
            send_message(self.transport, req)
            ans = get_message(self.transport)
        CLIENT_LOGGER.debug(f'Получен ответ {ans}')
        if RESPONSE in ans and ans[RESPONSE] == 202:
            for contact in ans[LIST_INFO]:
                self.database.add_contact(contact)
        else:
            CLIENT_LOGGER.error('Не удалось обновить список контактов.')

    def user_list_update(self):
        """
        Функция для обновления таблицы известных пользователей.
        :return:
        """
        CLIENT_LOGGER.debug(f'Запрос списка известных пользователей {self.username}')
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
            CLIENT_LOGGER.error('Не удалось обновить список известных пользователей.')

    def add_contact(self, contact):
        """
        Функция сообщающая на сервер о добавлении нового контакта.
        :param contact:
        :return:
        """
        CLIENT_LOGGER.debug(f'Создание контакта {contact}')
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
        Функция удаления клиента на сервере.
        :param contact:
        :return:
        """
        CLIENT_LOGGER.debug(f'Удаление контакта {contact}')
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
        Функция закрытия соединения, отправляет сообщение о выходе.
        :return:
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
        CLIENT_LOGGER.debug('Транспорт завершает работу.')
        time.sleep(0.5)

    def send_message(self, to, message):
        """
        Функция отправки сообщения на сервер.
        :param to:
        :param message:
        :return:
        """
        message_dict = {
            ACTION: MESSAGE,
            SENDER: self.username,
            DESTINATION: to,
            TIME: time.time(),
            MESSAGE_TEXT: message
        }
        CLIENT_LOGGER.debug(f'Сформирован словарь сообщения: {message_dict}')

        # Необходимо дождаться освобождения сокета для отправки сообщения.
        with socket_lock:
            send_message(self.transport, message_dict)
            self.process_server_ans(get_message(self.transport))
            CLIENT_LOGGER.info(f'Отправлено сообщение для пользователя {to}')

    def run(self):
        CLIENT_LOGGER.debug('Запущен процесс - приёмник сообщений с сервера.')
        while self.running:
            # Остановка на секунду, после попытка захватить сокет.
            time.sleep(1)
            with socket_lock:
                try:
                    self.transport.settimeout(1)
                    message = get_message(self.transport)
                except OSError as err:
                    if err.errno:
                        CLIENT_LOGGER.critical(f'Потеряно соединение с сервером.')
                        self.running = False
                        self.connection_lost.emit()
                # Проблемы с соединением
                except (
                        ConnectionError, ConnectionAbortedError, ConnectionResetError, json.JSONDecodeError,
                        TypeError):
                    CLIENT_LOGGER.debug(f'Потеряно соединение с сервером.')
                    self.running = False
                    self.connection_lost.emit()
                # Если сообщение получено, то вызываем функцию обработчик:
                else:
                    CLIENT_LOGGER.debug(f'Принято сообщение с сервера: {message}')
                    self.process_server_ans(message)
                finally:
                    self.transport.settimeout(5)
