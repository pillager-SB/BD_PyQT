import logging
import os

import logs.config_client_log
import argparse
import sys
from Cryptodome.PublicKey import RSA
from PyQt5.QtWidgets import QApplication, QMessageBox

from common.variables import *
from common.errors import ServerError
from common.decor import log
from client.database import ClientDatabase
from client.transport import ClientTransport
from client.main_window import ClientMainWindow
from client.start_dialog import UserNameDialog

logger = logging.getLogger('client')


# Парсер аргументов командной строки.
@log
def arg_parser():
    """
    Загрузка параметров из командной строки,
    при их отсутствии - обработка значений, принятых по умолчанию.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('addr', default=DEFAULT_IP_ADDRESS,
                        help='Reading an IP address', nargs='?')
    parser.add_argument('port', type=int, default=DEFAULT_PORT,
                        help='Read port IP address', nargs='?')
    parser.add_argument('-n', '--name', type=str, default=None,
                        help="Client's name", nargs='?')
    parser.add_argument('-p', '--password', default='',
                        help="Password", nargs='?')

    args = parser.parse_args(sys.argv[1:])
    server_address = args.addr
    server_port = args.port
    client_name = args.name
    client_passwd = args.password
    if server_port < 1024 or server_port > 65535:
        logger.critical(
            f'Номер {server_port} не является приемлемым номером порта. '
            f'Допустимы номера в диапазоне 1024-65535. '
            f'Клиент будет завершен.')
        sys.exit(1)

    return server_address, server_port, client_name, client_passwd


# Основная функция клиента.
if __name__ == '__main__':
    # Загрузка параметров из командной строки.
    server_address, server_port, client_name, client_passwd = arg_parser()

    # Создаю клиентское приложение.
    client_app = QApplication(sys.argv)

    # Если имя пользователя не было указано в командной строке то запросим его
    start_dialog = UserNameDialog()
    if not client_name or not client_passwd:
        client_app.exec_()
        # Если пользователь ввёл имя и нажал ОК, то сохраняем ведённое и
        # удаляем объект, иначе выходим.
        if start_dialog.ok_pressed:
            client_name = start_dialog.client_name.text()
            client_passwd = start_dialog.client_passwd.text()
            logger.debug(f'Using USERNAME = {client_name}, PASSWD = {client_passwd}.')
        else:
            exit(0)
    # Логирую события.
    logger.info(f'Запущен клиент с параметрами: '
                f'адрес сервера: {server_address}, '
                f'порт: {server_port}, '
                f'имя пользователя: {client_name}')

    # Загружаю ключи из файла, если же файла нет, то генерирую новую пару.
    dir_path = os.getcwd()
    key_file = os.path.join(dir_path, f'{client_name}.key')
    if not os.path.exists(key_file):
        keys = RSA.generate(2048, os.urandom)
        with open(key_file, 'wb') as key:
            key.write(keys.export_key())
    else:
        with open(key_file, 'rb') as key:
            keys = RSA.import_key(key.read())

    # !!!keys.publickey().export_key()
    logger.debug("Keys successfully loaded.")

    # Создаю объект клиентской базы данных.
    database = ClientDatabase(client_name)
    # Создаём объект - транспорт и запускаем транспортный поток
    try:
        transport = ClientTransport(
            server_port, server_address,
            database,
            client_name, client_passwd, keys)
        logger.debug("Транспорт готов.")

    except ServerError as error:
        message = QMessageBox()
        message.critical(start_dialog, 'Ошибка сервера', error.text)
        exit(1)
    transport.setDaemon(True)
    transport.start()

    del start_dialog

    # Создаю GUI.
    main_window = ClientMainWindow(database, transport, keys)
    main_window.make_connection(transport)
    main_window.setWindowTitle(f'Чат-программа L6 release- {client_name}')
    client_app.exec_()

    # Раз графическая оболочка закрылась, закрываем транспорт
    transport.transport_shutdown()
    transport.join()
