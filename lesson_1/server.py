import configparser
import argparse
import sys
import os
import select
import socket
import threading

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox

from common.variables import *
from common.utils import send_message, get_message
from common.decor import Log
from deskriptors import PortValidator
from metaclases import ServerVerifier
from server_database import ServerStorage
from server_gui import MainWindow, ConfigWindow, create_stat_model, HistoryWindow, gui_create_model

sys.path.append(os.path.join(os.getcwd(), '..'))

new_connection = False
conflag_lock = threading.Lock()
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


class Server(threading.Thread, metaclass=ServerVerifier):
    # Проверка получения корректного номера порта для работы сервера.
    port = PortValidator()

    def __init__(self, listen_address, listen_port, database):
        self.addr = listen_address
        self.port = listen_port
        #  База данных сервера.
        self.database = database
        #  Списки:
        self.clients = []  # Список клиентов.
        self.messages = []  # Список очереди сообщений.
        # Словарь, содержащий имена пользователей и соответствующие им сокеты.
        self.names = dict()  # {client_name: client_socket}

        super().__init__()

    def init_socket(self):
        SERVER_LOGGER.info(f'Запущен сервер, порт для подключений: {self.port}, '
                           f'адрес с которого принимаются подключения: {self.addr}. '
                           f'Если адрес не указан, принимаются соединения с любых адресов.')

        # Готовим сокет.
        transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        transport.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        transport.bind((self.addr, self.port))
        transport.settimeout(0.5)

        # Слушаем сокет.
        self.sock = transport
        self.sock.listen()

    def run(self):
        # Инициализирую сокет.
        self.init_socket()
        # Основной цикл программы сервера.
        while True:
            #  Ожидаю подключения, если timeout пройден, безопасно ловлю исключение.
            try:
                client, client_address = self.sock.accept()
            except OSError as e:
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
            except OSError as err:
                SERVER_LOGGER.error(f'Ошибка работы с сокетами: {err}')

            # Принимаю сообщение, если ошибка - исключаю клиента.
            if recv_data_lst:
                for client_with_message in recv_data_lst:
                    try:
                        self.process_client_message(
                            get_message(client_with_message), client_with_message)
                    except OSError as e:
                        # Ищем клиента в словаре клиентов и удаляем его из него
                        # и из базы подключённых.
                        SERVER_LOGGER.info(
                            f'Клиент {client_with_message.getpeername()} отключился от сервера. {e}')
                        for name in self.names:
                            if self.names[name] == client_with_message:
                                self.database.user_logout(name)
                                del self.names[name]
                                break
                        self.clients.remove(client_with_message)

            # Если есть сообщения, обрабатываем каждое.
            for message in self.messages:
                try:
                    self.process_message(message, send_data_lst)
                except Exception as e:
                    SERVER_LOGGER.info(f'Связь с клиентом {message[DESTINATION]} была утеряна.'
                                       f'ошибка {e}')
                    self.clients.remove(self.names[message[DESTINATION]])
                    self.database.user_logout(message[DESTINATION])
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
        global new_connection
        SERVER_LOGGER.debug(f'Разбор сообщения от клиента : {message}')
        # Если это сообщение о присутствии, принимаю и отвечаю.
        if ACTION in message and message[ACTION] == PRESENCE and TIME in message \
                and USER in message:
            # Если такого пользователя нет, регистрация, иначе - отправка ответа и завершение соединения.
            if message[USER][ACCOUNT_NAME] not in self.names.keys():
                self.names[message[USER][ACCOUNT_NAME]] = client
                client_ip, client_port = client.getpeername()
                self.database.user_login(message[USER][ACCOUNT_NAME], client_ip, client_port)
                send_message(client, {RESPONSE: 200})  # Если правильное сообщение о присутствии, принимаем и отвечаем.
                with conflag_lock:
                    new_connection = True
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
                and MESSAGE_TEXT in message \
                and self.names[message[SENDER]] == client:
            self.messages.append(message)  # Если это сообщение, ставим его в очередь сообщений.
            self.database.process_message(
                message[SENDER], message[DESTINATION])
            return

        elif ACTION in message \
                and message[ACTION] == EXIT \
                and ACCOUNT_NAME in message \
                and self.names[message[ACCOUNT_NAME]] == client:
            self.database.user_logout(message[ACCOUNT_NAME])
            SERVER_LOGGER.info(
                f'Клиент {message[ACCOUNT_NAME]} корректно отключился от сервера.')
            self.clients.remove(self.names[message[ACCOUNT_NAME]])
            self.names[message[ACCOUNT_NAME]].close()
            del self.names[message[ACCOUNT_NAME]]
            with conflag_lock:
                new_connection = True
            return

        elif ACTION in message and message[ACTION] == GET_CONTACTS \
                and USER in message \
                and self.names[message[USER]] == client:
            response = RESPONSE_202
            response[LIST_INFO] = self.database.get_contacts(message[USER])
            send_message(client, response)

        # Если это добавление контакта
        elif ACTION in message and message[ACTION] == ADD_CONTACT and ACCOUNT_NAME in message and USER in message \
                and self.names[message[USER]] == client:
            self.database.add_contact(message[USER], message[ACCOUNT_NAME])
            send_message(client, RESPONSE_200)

        # Если это удаление контакта

        elif ACTION in message and message[ACTION] == REMOVE_CONTACT and ACCOUNT_NAME in message and USER in message \
                and self.names[message[USER]] == client:
            self.database.remove_contact(message[USER], message[ACCOUNT_NAME])
            send_message(client, RESPONSE_200)

        # Если это запрос известных пользователей
        elif ACTION in message and message[ACTION] == USERS_REQUEST and ACCOUNT_NAME in message \
                and self.names[message[ACCOUNT_NAME]] == client:
            response = RESPONSE_202
            response[LIST_INFO] = [user[0]
                                   for user in self.database.users_list()]
            send_message(client, response)
        else:
            send_message(client, {RESPONSE: 400, ERROR: 'Запрос некорректен.'})  # Отправляем сообщение о том,
            # что сервер не смог понять запрос.
            return


@Log(SERVER_LOGGER)
def main():
    # Загрузка файла конфигурации сервера
    config = configparser.ConfigParser()

    dir_path = os.path.dirname(os.path.realpath(__file__))
    config.read(f"{dir_path}/{'server.ini'}")

    # Загрузка параметров командной строки, если нет параметров, то задаём
    # значения по умолчанию.
    listen_address, listen_port = arg_parser()

    # Инициализирую базу данных.
    database = ServerStorage()

    # Создаю экземпляр класса сервера и запускаю его.
    server = Server(listen_address, listen_port, database)
    server.daemon = True
    server.start()

    # Создаём графическое окружение для сервера:
    server_app = QApplication(sys.argv)
    main_window = MainWindow()

    # Инициализируем параметры в окна
    main_window.statusBar().showMessage('Server Working')
    main_window.active_clients_table.setModel(gui_create_model(database))
    main_window.active_clients_table.resizeColumnsToContents()
    main_window.active_clients_table.resizeRowsToContents()

    # Функция обновляющая список подключённых, проверяет флаг подключения, и
    # если надо обновляет список
    def list_update():
        global new_connection
        if new_connection:
            main_window.active_clients_table.setModel(
                gui_create_model(database))
            main_window.active_clients_table.resizeColumnsToContents()
            main_window.active_clients_table.resizeRowsToContents()
            with conflag_lock:
                new_connection = False

    # Функция создающая окно со статистикой клиентов
    def show_statistics():
        global stat_window
        stat_window = HistoryWindow()
        stat_window.history_table.setModel(create_stat_model(database))
        stat_window.history_table.resizeColumnsToContents()
        stat_window.history_table.resizeRowsToContents()
        stat_window.show()

    # Функция создающая окно с настройками сервера.
    def server_config():
        global config_window
        # Создаём окно и заносим в него текущие параметры
        config_window = ConfigWindow()
        config_window.db_path.insert(config['SETTINGS']['Database_path'])
        config_window.db_file.insert(config['SETTINGS']['Database_file'])
        config_window.port.insert(config['SETTINGS']['Default_port'])
        config_window.ip.insert(config['SETTINGS']['Listen_Address'])
        config_window.save_btn.clicked.connect(save_server_config)

    # Функция сохранения настроек
    def save_server_config():
        global config_window
        message = QMessageBox()
        config['SETTINGS']['Database_path'] = config_window.db_path.text()
        config['SETTINGS']['Database_file'] = config_window.db_file.text()
        try:
            port = int(config_window.port.text())
        except ValueError:
            message.warning(config_window, 'Ошибка', 'Порт должен быть числом')
        else:
            config['SETTINGS']['Listen_Address'] = config_window.ip.text()
            if 1023 < port < 65536:
                config['SETTINGS']['Default_port'] = str(port)
                print(port)
                with open('server.ini', 'w') as conf:
                    config.write(conf)
                    message.information(
                        config_window, 'OK', 'Настройки успешно сохранены!')
            else:
                message.warning(
                    config_window,
                    'Ошибка',
                    'Порт должен быть от 1024 до 65536')

    # Таймер, обновляющий список клиентов 1 раз в секунду
    timer = QTimer()
    timer.timeout.connect(list_update)
    timer.start(1000)

    # Связываем кнопки с процедурами
    main_window.refresh_button.triggered.connect(list_update)
    main_window.show_history_button.triggered.connect(show_statistics)
    main_window.config_btn.triggered.connect(server_config)

    # Запускаем GUI
    server_app.exec_()




if __name__ == '__main__':
    main()

