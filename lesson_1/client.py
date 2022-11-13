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

CLIENT_LOGGER = logging.getLogger('client')


@Log(CLIENT_LOGGER)
def create_exit_message(account_name):
    """Формирую сообщение-словарь для выхода клиента account_name."""
    return {
        ACTION: EXIT,
        TIME: time.time(),
        ACCOUNT_NAME: account_name
    }


@Log(CLIENT_LOGGER)
def message_from_server(sock, my_username):
    """Функция - обработчик сообщений других пользователей, поступающих с сервера"""
    while True:
        try:
            message = get_message(sock)
            if ACTION in message and message[ACTION] == MESSAGE and \
                    SENDER in message and DESTINATION in message and \
                    MESSAGE_TEXT in message and message[DESTINATION] == my_username:
                print(f'\nПолучено сообщение от пользователя '
                      f'{message[SENDER]}:\n{message[MESSAGE_TEXT]}')
                CLIENT_LOGGER.info(f'Получено сообщение от пользователя {message[SENDER]}:\n{message[MESSAGE_TEXT]}')
            else:
                CLIENT_LOGGER.error(f'Получено некорректное сообщение с сервера: {message}')
        except IncorrectDataReceivedError:
            CLIENT_LOGGER.error(f'Не удалось декодировать полученное сообщение.')
        except (OSError, ConnectionError, json.JSONDecodeError):
            CLIENT_LOGGER.critical(f'Потеряно соединение с сервером.')
            break


@Log(CLIENT_LOGGER)
def create_message(sock, account_name='Guest'):
    """Функция формирует сообщение-словарь с указанием получателя и отправляет его на сервер"""
    to_user = input('Введите получателя сообщения: ')
    message = input('Введите сообщение для отправки: ')
    message_dict = {
        ACTION: MESSAGE,
        SENDER: account_name,
        DESTINATION: to_user,
        TIME: time.time(),
        MESSAGE_TEXT: message
    }
    CLIENT_LOGGER.debug(f'Сформирован словарь сообщения: {message_dict}')
    try:
        send_message(sock, message_dict)
        CLIENT_LOGGER.info(f'Отправлено {message} для пользователя {to_user}')
    except Exception as e:
        print(e)
        CLIENT_LOGGER.critical('Потеряно соединение с сервером.')
        sys.exit(1)


@Log(CLIENT_LOGGER)
def user_interactive(sock, username):
    """Функция для взаимодействия с пользователем"""
    print(HELP)
    while True:
        command = input('Введите команду: ')
        match command:
            case '-m' | 'message':
                create_message(sock, username)
            case '-h' | '-?' | 'help':
                print(HELP)
            case '-e' | 'exit':
                send_message(sock, create_exit_message(username))
                print('Завершение соединения.')
                CLIENT_LOGGER.info('Работа завершена по команде пользователя.')
                time.sleep(0.5)
                break
            case _:
                print('Команда не распознана, попробуйте снова. -? - вывести список команд.')


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
        return f'400 : {message[ERROR]}'
    raise ReqFieldMissingError(RESPONSE)


@Log(CLIENT_LOGGER)
def main():
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
    #  Вывод сообщения о запуске клиента.
    print(f'Консольный мессенджер. Клиентский модуль.\nИмя пользователя: {client_name}')
    # Запрос имени пользователя, если оно не задано.
    if not client_name:
        client_name = input('Введите имя пользователя: ')

    CLIENT_LOGGER.info(f'Запущен клиент с параметрами: адрес сервера: {server_address}, '
                       f'порт: {server_port}, имя пользователя: {client_name}')

    #  Инициализация сокета и обмен.
    try:
        transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
        # Если соединение установлено корректно,
        # запуск процесса приема сообщения.
        receiver = threading.Thread(target=message_from_server, args=(transport, client_name))
        receiver.daemon = True
        receiver.start()

        # Взаимодействие с пользователем и отправка сообщений.
        user_interface = threading.Thread(target=user_interactive, args=(transport, client_name))
        user_interface.daemon = True
        user_interface.start()
        CLIENT_LOGGER.debug('Запущены процессы')
        # Проверка, живы ли оба потока, если да - продолжаем, нет - прерываем цикл.
        while True:
            time.sleep(1)
            if receiver.is_alive() and user_interface.is_alive():
                continue
            break


if __name__ == '__main__':
    main()
