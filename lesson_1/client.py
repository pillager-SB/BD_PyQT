import argparse
import json
import sys
import threading
import time
import socket
from common.variables import *
from common.utils import send_message, get_message

import logging
import logs.config_client_log
from errors import ReqFieldMissingError, NonDictInputError, ServerError, IncorrectDataReceivedError
from decor import Log
from metaclases import ClientVerifier
from client_database import ClientDatabase

CLIENT_LOGGER = logging.getLogger('client')
# Объект блокировки сокета и работы с базой данных
sock_lock = threading.Lock()
database_lock = threading.Lock()


# Класс для формирования и отправки сообщений на сервер и для взаимодействия с пользователем.
class ClientSender(threading.Thread, metaclass=ClientVerifier):
    def __init__(self, account_name, sock, database):
        self.account_name = account_name
        self.sock = sock
        self.database = database
        super().__init__()

    @Log(CLIENT_LOGGER)
    def create_exit_message(self):
        """
        Функция формирует и отдает словарь с сообщением о выходе.
        """
        return {
            ACTION: EXIT,
            TIME: time.time(),
            ACCOUNT_NAME: self.account_name
        }

    @Log(CLIENT_LOGGER)
    def create_message(self):
        """Функция формирует сообщение-словарь с указанием получателя
        и отправляет его на сервер"""
        to_user = input('Введите получателя сообщения: ')
        message = input('Введите сообщение для отправки: ')
        with database_lock:
            if not self.database.check_user(to_user):
                CLIENT_LOGGER.error(
                    f'Попытка отправить сообщение незарегистрированному получателю: {to_user}')
                return

        message_dict = {
            ACTION: MESSAGE,
            SENDER: self.account_name,
            DESTINATION: to_user,
            TIME: time.time(),
            MESSAGE_TEXT: message
        }
        CLIENT_LOGGER.debug(f'Сформирован словарь сообщения: {message_dict}')

        # Сохраняем сообщения для истории
        with database_lock:
            self.database.save_message(self.account_name, to_user, message)

        # Необходимо дождаться освобождения сокета для отправки сообщения
        with sock_lock:
            try:
                send_message(self.sock, message_dict)
                CLIENT_LOGGER.info(f'Отправлено {message} для пользователя {to_user}')
            except OSError as err:
                if err.errno:
                    CLIENT_LOGGER.critical('Потеряно соединение с сервером.')
                    exit(1)
                else:
                    CLIENT_LOGGER.error('Не удалось передать сообщение. Таймаут соединения')

    # @Log(CLIENT_LOGGER)
    def run(self):
        """Функция для взаимодействия с пользователем"""
        print(HELP)
        while True:
            command = input('Введите команду: ')
            match command:
                case '-m' | 'message':
                    self.create_message()
                case '-?' | 'help':
                    print(HELP)
                case '-q' | 'exit':
                    send_message(self.sock, self.create_exit_message())
                    print('Завершение соединения.')
                    CLIENT_LOGGER.info('Работа завершена по команде пользователя.')
                    time.sleep(0.5)
                    break
                case '-c' | 'contacts':
                    with database_lock:
                        contacts_list = self.database.get_contacts()
                    for contact in contacts_list:
                        print(contact)
                case '-e' | 'edit':
                    self.edit_contacts()
                case '-h' | 'history':
                    self.print_history()
                case _:
                    print('Команда не распознана, попробуйте снова. -? - вывести список команд.')

    def print_history(self):
        """
        Функция выводящая историю сообщений.
        :return:
        """
        ask = input('Показать входящие сообщения - in, исходящие - out, все - просто Enter: ')
        with database_lock:
            if ask == 'in':
                history_list = self.database.get_history(to_who=self.account_name)
                for message in history_list:
                    print(f'\nСообщение от пользователя: {message[0]} от {message[3]}:\n{message[2]}')
            elif ask == 'out':
                history_list = self.database.get_history(from_who=self.account_name)
                for message in history_list:
                    print(f'\nСообщение пользователю: {message[1]} от {message[3]}:\n{message[2]}')
            else:
                history_list = self.database.get_history()
                for message in history_list:
                    print(
                        f'\nСообщение от пользователя: {message[0]}, пользователю {message[1]} '
                        f'от {message[3]}\n{message[2]}')

    def edit_contacts(self):
        """
        Функция редактирования контактов.
        :return:
        """
        ans = input('Для удаления введите del, для добавления add: ')
        if ans == 'del':
            edit = input('Введите имя удаляемого контакта: ')
            with database_lock:
                if self.database.check_contact(edit):
                    self.database.del_contact(edit)
                    print(f'Контакт {edit} успешно удален.')
                else:
                    print(f'Контакт {edit} не найден.')
                    CLIENT_LOGGER.error('Попытка удаления несуществующего контакта.')
        elif ans == 'add':
            edit = input('Введите имя создаваемого контакта: ')
            # Проверка на возможность такого контакта
            if self.database.check_user(edit):
                with database_lock:
                    self.database.add_contact(edit)
                with sock_lock:
                    try:
                        add_contact(self.sock, self.account_name, edit)
                    except ServerError:
                        CLIENT_LOGGER.error('Не удалось отправить информацию на сервер.')


# Класс для приема сообщений с сервера. Принимает сообщения, выводит в консоль.
class ClientReader(threading.Thread, metaclass=ClientVerifier):
    def __init__(self, account_name, sock, database):
        self.account_name = account_name
        self.sock = sock
        self.database = database
        super().__init__()

    # Основной цикл приёмника сообщений, принимает сообщения, выводит в консоль. Завершается при потере соединения.
    def run(self):
        """Функция - обработчик сообщений других пользователей, поступающих с сервера"""
        while True:
            time.sleep(1)
            with sock_lock:
                try:
                    message = get_message(self.sock)
                except IncorrectDataReceivedError:
                    CLIENT_LOGGER.error(f'Не удалось декодировать полученное сообщение.')
                # Вышел таймаут соединения если errno = None, иначе обрыв соединения.
                except OSError as err:
                    if err.errno:
                        CLIENT_LOGGER.critical(f'Потеряно соединение с сервером.')
                        break
                # Проблемы с соединением.
                except (OSError, ConnectionError, json.JSONDecodeError) as err:
                    CLIENT_LOGGER.critical(f'Потеряно соединение с сервером. {err}')
                    break
                    # Если пакет корректно получен выводим в консоль и записываем в базу.
                else:
                    if ACTION in message and message[ACTION] == MESSAGE and \
                            SENDER in message and DESTINATION in message and \
                            MESSAGE_TEXT in message and message[DESTINATION] == self.account_name:
                        print(f'\nПолучено сообщение от пользователя '
                              f'{message[SENDER]}:\n{message[MESSAGE_TEXT]}')
                        with database_lock:
                            try:
                                self.database.save_message(message[SENDER],
                                                           self.account_name,
                                                           message[MESSAGE_TEXT])
                            except:
                                CLIENT_LOGGER.error('Ошибка взаимодействия с базой данных')

                        CLIENT_LOGGER.info(
                            f'Получено сообщение от пользователя {message[SENDER]}:\n{message[MESSAGE_TEXT]}')
                    else:
                        CLIENT_LOGGER.error(f'Получено некорректное сообщение с сервера: {message}')


@Log(CLIENT_LOGGER)
def create_presence(account_name):
    """Функция создает словарь-запрос о присутствии клиента"""
    out = {
        ACTION: PRESENCE,
        TIME: time.time(),
        USER: {
            ACCOUNT_NAME: account_name
        }
    }
    CLIENT_LOGGER.debug(f'Сформировано {PRESENCE} сообщение для пользователя {account_name}')
    return out


@Log(CLIENT_LOGGER)
def process_ans(message):
    """Функция разбирающая ответ сервера"""
    CLIENT_LOGGER.debug(f'Разбор ответа сервера: {message}')
    if RESPONSE in message:
        if message[RESPONSE] == 200:
            return '200 : Ok!'
        elif message[RESPONSE] == 400:
            raise ServerError(f'400 : {message[ERROR]}')
    raise ReqFieldMissingError(RESPONSE)


# Парсер аргументов командной строки.
@Log(CLIENT_LOGGER)
def arg_parser():
    """
    Загрузка параметров из командной строки,
    при их отсутствии - обработка значений, принятых по умолчанию.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('addr', default=DEFAULT_IP_ADDRESS, help='Reading an IP address', nargs='?')
    parser.add_argument('port', type=int, default=DEFAULT_PORT, help='Read port IP address', nargs='?')
    parser.add_argument('-n', '--name', type=str, default=None, help="Client's name", nargs='?')

    args = parser.parse_args()
    server_address = args.addr
    server_port = args.port
    client_name = args.name

    if server_port < 1024 or server_port > 65535:
        CLIENT_LOGGER.critical(
            f'Номер {server_port} не является приемлемым номером порта. '
            f'Допустимы номера в диапазоне 1024-65535. '
            f'Клиент будет завершен.')
        sys.exit(1)

    return server_address, server_port, client_name


def contacts_list_request(sock, name):
    """
    Функция запрашивающая контакт-лист.
    :param sock:
    :param name:
    :return:
    """
    CLIENT_LOGGER.debug(f'Запрос контакт листа для пользователя {name}.')
    req = {
        ACTION: GET_CONTACTS,
        TIME: time.time(),
        USER: name
    }
    CLIENT_LOGGER.debug(f'Сформирован запрос {req}')
    send_message(sock, req)
    ans = get_message(sock)
    CLIENT_LOGGER.debug(f'Получен ответ {ans}')
    if RESPONSE in ans and ans[RESPONSE] == 202:
        return ans[LIST_INFO]
    else:
        raise ServerError


def add_contact(sock, username, contact):
    """
    Функция добавляющая пользователя в контакт лист.
    :param sock:
    :param username:
    :param contact:
    :return:
    """
    CLIENT_LOGGER.debug(f'Создание контакта {contact}')
    req = {
        ACTION: ADD_CONTACT,
        TIME: time.time(),
        USER: username,
        ACCOUNT_NAME: contact
    }
    send_message(sock, req)
    ans = get_message(sock)
    if RESPONSE in ans and ans[RESPONSE] == 200:
        pass
    else:
        raise ServerError('Ошибка создания контакта')
    print('Удачное создание контакта.')


def user_list_request(sock, username):
    """
    Функция запрашивающая список известных пользователей.
    :param sock:
    :param username:
    :return:
    """
    CLIENT_LOGGER.debug(f'Запрос списка известных пользователей {username}')
    req = {
        ACTION: USERS_REQUEST,
        TIME: time.time(),
        ACCOUNT_NAME: username
    }
    send_message(sock, req)
    ans = get_message(sock)
    if RESPONSE in ans and ans[RESPONSE] == 202:
        return ans[LIST_INFO]
    else:
        raise ServerError


def remove_contact(sock, username, contact):
    """
    Функция удаляющая пользователя из контакт-листа.
    :param sock:
    :param username:
    :param contact:
    :return:
    """
    CLIENT_LOGGER.debug(f'Создание контакта {contact}')
    req = {
        ACTION: REMOVE_CONTACT,
        TIME: time.time(),
        USER: username,
        ACCOUNT_NAME: contact
    }
    send_message(sock, req)
    ans = get_message(sock)
    if RESPONSE in ans and ans[RESPONSE] == 200:
        pass
    else:
        raise ServerError('Ошибка удаления клиента')
    print('Удачное удаление')


# Функция инициализатор базы данных. Запускается при запуске, загружает данные в базу с сервера.
def database_load(sock, database, username):
    # Загружаем список известных пользователей
    try:
        users_list = user_list_request(sock, username)
    except ServerError:
        CLIENT_LOGGER.error('Ошибка запроса списка известных пользователей.')
    else:
        database.add_users(users_list)

    # Загружаем список контактов
    try:
        contacts_list = contacts_list_request(sock, username)
    except ServerError:
        CLIENT_LOGGER.error('Ошибка запроса списка контактов.')
    else:
        for contact in contacts_list:
            database.add_contact(contact)


@Log(CLIENT_LOGGER)
def main():
    #  Вывод сообщения о запуске клиента.
    print(f'Консольный мессенджер. Клиентский модуль.')
    # Загрузка параметров из командной строки.
    server_address, server_port, client_name = arg_parser()
    # Запрос имени пользователя, если оно не задано.
    if not client_name:
        client_name = input('Введите имя пользователя: ')
    else:
        print(f'Клиентский модуль запущен с именем: {client_name}')

    CLIENT_LOGGER.info(f'Запущен клиент с параметрами: адрес сервера: {server_address}, '
                       f'порт: {server_port}, имя пользователя: {client_name}')

    #  Инициализация сокета и обмен.
    try:
        transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Таймаут 1 секунда, необходим для освобождения сокета.
        transport.settimeout(1)
        transport.connect((server_address, server_port))
        send_message(transport, create_presence(client_name))
        answer = process_ans(get_message(transport))
        CLIENT_LOGGER.info(f'Установлено соединение с сервером. Ответ сервера: {answer}')
        print('Установлено соединение с сервером.')
    except json.JSONDecodeError:
        CLIENT_LOGGER.error('Не удалось декодировать сообщение сервера.')
        sys.exit(1)
    except ServerError as error:
        CLIENT_LOGGER.error(f'При установке соединения сервер вернул ошибку: {error.text}')
        sys.exit(1)
    except ReqFieldMissingError as missing_error:
        CLIENT_LOGGER.error(f'В ответе сервера отсутствует необходимое поле '
                            f'{missing_error.missing_field}')
        sys.exit(1)
    except NonDictInputError:
        CLIENT_LOGGER.critical(f'Аргумент функции должен быть словарём.')
        sys.exit(1)
    except ConnectionRefusedError:
        CLIENT_LOGGER.critical(f'Не удалось подключиться к серверу {server_address}:{server_port}, '
                               f'конечный компьютер отверг запрос на подключение.')
        sys.exit(1)
    except TimeoutError:
        CLIENT_LOGGER.critical(f'Попытка установить соединение была безуспешной, т.к. от '
                               f'{server_address}:{server_port} за требуемое время не получен нужный отклик, '
                               f'или было разорвано уже установленное соединение из-за неверного отклика '
                               f'уже подключенного компьютера')
        sys.exit(1)
    else:
        # Инициализация БД
        database = ClientDatabase(client_name)
        database_load(transport, database, client_name)

        # Если соединение установлено корректно,
        # взаимодействие с пользователем и отправка сообщений.
        user_interface = ClientSender(client_name, transport, database)
        user_interface.daemon = True
        user_interface.start()
        CLIENT_LOGGER.debug('Запущены процессы')

        # запуск процесса приема сообщения.
        receiver = ClientReader(client_name, transport, database)
        receiver.daemon = True
        receiver.start()

        # Проверка, живы ли оба потока, если да - продолжаем, нет - прерываем цикл.
        while True:
            time.sleep(1)
            if receiver.is_alive() and user_interface.is_alive():
                continue
            break


if __name__ == '__main__':
    main()
