import argparse
import json
import sys
import socket
import select
import time
import logging
import logs.config_server_log
from common.variables import *
from common.utils import send_message, get_message
from decor import Log
from lesson_1.deskriptors import PortValidator
from lesson_1.metaclases import ServerVerifier

SERVER_LOGGER = logging.getLogger('server')


@Log(SERVER_LOGGER)
def arg_parser():
    """
    Загрузка параметров из командной строки,
    при их отсутствии - обработка значений, принятых по умолчанию.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--addr', default='', help='Reading an IP address', nargs='?')
    parser.add_argument('-p', '--port', default=DEFAULT_PORT, type=int, help='Read port IP address', nargs='?')
    args = parser.parse_args()
    listen_address = args.addr
    listen_port = args.port
    return listen_address, listen_port


class Server(metaclass=ServerVerifier):
    # # Проверка получения корректного номера порта для работы сервера.
    # listen_port = PortValidator('listen_port')
    port = PortValidator()

    def __init__(self, listen_address, listen_port):
        self.addr = listen_address
        self.port = listen_port
        #  Списки:
        self.clients = []  # Список клиентов.
        self.messages = []  # Список очереди сообщений.
        # Словарь, содержащий имена пользователей и соответствующие им сокеты.
        self.names = dict()  # {client_name: client_socket}

    def init_socket(self):
        SERVER_LOGGER.info(f'Запущен сервер, порт для подключений: {self.port}, '
                           f'адрес с которого принимаются подключения: {self.addr}. '
                           f'Если адрес не указан, принимаются соединения с любых адресов.')

        # Готовим сокет.
        transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        transport.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        transport.bind((self.addr, self.port))
        transport.settimeout(0.5)

        # Слушаем порт.
        self.sock = transport
        self.sock.listen(MAX_CONNECTION)

    def main_loop(self):
        # Инициализирую сокет.
        self.init_socket()
        # Основной цикл программы сервера.
        while True:
            #  Ожидаю подключения, если timeout пройден, безопасно ловлю исключение.
            try:
                client, client_address = self.sock.accept()
            except OSError:
                ...
            else:
                SERVER_LOGGER.info(f'Установлено соединение с ПК {client_address}')
                self.clients.append(client)

            recv_data_lst = []
            send_data_lst = []
            err_lst = []

            # Проверяю, есть ли клиенты в списке.
            try:
                if self.clients:
                    recv_data_lst, send_data_lst, err_lst = select.select(self.clients, self.clients, [], 0)
            except OSError:
                ...
            # Принимаю сообщение, если ошибка - исключаю клиента.
            if recv_data_lst:
                for client_with_message in recv_data_lst:
                    try:
                        self.process_client_message(get_message(client_with_message), client_with_message)
                    except Exception as e:
                        SERVER_LOGGER.info(f'Клиент {client_with_message.getpeername()} отключился от сервера. {e}')
                        self.clients.remove(client_with_message)

            # Если есть сообщения, обрабатываем каждое.
            if self.messages:
                for message in self.messages:
                    try:
                        self.process_message(message, send_data_lst)

                    except Exception as e:
                        SERVER_LOGGER.info(f'Связь с клиентом {message[DESTINATION]} была утеряна.'
                                           f'ошибка {e}')
                        self.clients.remove(self.names[message[DESTINATION]])
                        del self.names[message[DESTINATION]]
                self.messages.clear()

    @Log(SERVER_LOGGER)
    def process_message(self, message, lst_sock):
        """Функция адресной отправки сообщения определенному клиенту"""
        if message[DESTINATION] in self.names and self.names[message[DESTINATION]] in lst_sock:
            send_message(self.names[message[DESTINATION]], message)
            SERVER_LOGGER.info(f'Отправлено сообщение пользователю {message[DESTINATION]} '
                               f'от пользователя {message[SENDER]}.')
        elif message[DESTINATION] in self.names and self.names[message[DESTINATION]] not in lst_sock:
            raise ConnectionError
        else:
            SERVER_LOGGER.error(
                f'Пользователь {message[DESTINATION]} не зарегистрирован на сервере, '
                f'отправка сообщения невозможна.')

    @Log(SERVER_LOGGER)
    def process_client_message(self, message, client):
        """
        Функция-обработчик сообщений от клиентов, принимает словарь-сообщение,
        проверяет корректность, возвращает словарь-ответ для клиента.
        """
        SERVER_LOGGER.debug(f'Разбор сообщения от клиента : {message}')
        # Если это сообщение о присутствии, принимаю и отвечаю.
        if ACTION in message and message[ACTION] == PRESENCE and TIME in message \
                and USER in message:
            # Если такого пользователя нет, регистрация, иначе - отправка ответа и завершение соединения.
            if message[USER][ACCOUNT_NAME] not in self.names.keys():
                self.names[message[USER][ACCOUNT_NAME]] = client
                send_message(client, {RESPONSE: 200})  # Если правильное сообщение о присутствии, принимаем и отвечаем.
            else:
                send_message(client, {RESPONSE: 400, ERROR: 'Имя пользователя уже занято.'})
                self.clients.remove(client)
                client.close()
            return
        elif ACTION in message \
                and message[ACTION] == MESSAGE \
                and DESTINATION in message \
                and TIME in message \
                and SENDER in message \
                and MESSAGE_TEXT in message:
            self.messages.append(message)  # Если это сообщение, ставим его в очередь сообщений.
            return
        elif ACTION in message \
                and message[ACTION] == EXIT \
                and ACCOUNT_NAME in message:
            self.clients.remove(self.names[ACCOUNT_NAME])
            self.names[ACCOUNT_NAME].close()
            del self.names[ACCOUNT_NAME]
            return
        else:
            send_message(client, {RESPONSE: 400, ERROR: 'Запрос некорректен.'})  # Отправляем сообщение о том,
            # что сервер не смог понять запрос.
            return


@Log(SERVER_LOGGER)
def main():
    listen_address, listen_port = arg_parser()
    server = Server(listen_address, listen_port)
    server.main_loop()


if __name__ == '__main__':
    main()
