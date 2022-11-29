import logging
import logs.config_client_log
import argparse
import sys
from PyQt5.QtWidgets import QApplication
from common.variables import *
from common.errors import ServerError
from common.decor import Log
from client.database import ClientDatabase
from client.transport import ClientTransport
from client.main_window import ClientMainWindow
from client.start_dialog import UserNameDialog

CLIENT_LOGGER = logging.getLogger('client')


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


# Основная функция клиента.
if __name__ == '__main__':
    # Загрузка параметров из командной строки.
    server_address, server_port, client_name = arg_parser()

    # Создаю клиентское приложение.
    client_app = QApplication(sys.argv)

    # Запрос имени пользователя, если оно не задано в КС.
    if not client_name:
        start_dialog = UserNameDialog()
        client_app.exec_()
        client_name = input('Введите имя пользователя: ')
        # Если пользователь ввел имя и нажал "Ok!",
        # сохраняю введенное имя и удаляю диалог,
        # иначе - выход.
        if start_dialog.ok_pressed:
            client_name = start_dialog.client_name.text()
            del start_dialog
        else:
            exit(0)
    # Логирую события.
    CLIENT_LOGGER.info(f'Запущен клиент с параметрами: '
                       f'адрес сервера: {server_address}, '
                       f'порт: {server_port}, '
                       f'имя пользователя: {client_name}')

    # Создаю объект клиентской базы данных.
    database = ClientDatabase(client_name)
    # Создаём объект - транспорт и запускаем транспортный поток
    try:
        transport = ClientTransport(server_port, server_address, database, client_name)
    except ServerError as error:
        print(error.text)
        exit(1)
    transport.setDaemon(True)
    transport.start()

    # Создаю GUI.
    main_window = ClientMainWindow(database, transport)
    main_window.make_connection(transport)
    main_window.setWindowTitle(f'Чат Программа alpha release - {client_name}')
    client_app.exec_()

    # Раз графическая оболочка закрылась, закрываем транспорт
    transport.transport_shutdown()
    transport.join()

