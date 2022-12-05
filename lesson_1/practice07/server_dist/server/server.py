import argparse
import configparser
import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from common.decor import log
from common.utils import *
from server.core import MessageProcessor
from server.main_window import MainWindow
from server.database import ServerStorage

sys.path.append(os.path.join(os.getcwd(), '..'))

# Инициализация логирования сервера.
logger = logging.getLogger('server')


@log
def arg_parser(default_port, default_address):
    """
    Загрузка параметров из командной строки,
    при их отсутствии - обработка значений, принятых по умолчанию.
    """
    logger.debug(
        f'Инициализация парсера аргументов командной строки: {sys.argv}')
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=DEFAULT_PORT, type=int, help='Read port IP address', nargs='?')
    parser.add_argument('-a', '--addr', default='', help='Reading an IP address', nargs='?')
    parser.add_argument('-no_gui', action='store_true')
    args = parser.parse_args(sys.argv[1:])
    listen_address = args.addr
    listen_port = args.port
    gui_flag = args.no_gui
    return listen_address, listen_port, gui_flag


@log
def config_load():
    """Парсер конфигурационного ini файла."""
    config = configparser.ConfigParser()
    dir_path = os.getcwd()
    config.read(f"{dir_path}/{'server.ini'}")
    # Если конфиг файл загружен правильно, запускаемся, иначе конфиг по
    # умолчанию.
    if 'SETTINGS' in config:
        return config
    else:
        config.add_section('SETTINGS')
        config.set('SETTINGS', 'Default_port', str(DEFAULT_PORT))
        config.set('SETTINGS', 'Listen_Address', '')
        config.set('SETTINGS', 'Database_path', '')
        config.set('SETTINGS', 'Database_file', 'server_database.db3')
        return config


@log
def main():
    """Основная функция"""
    # Загрузка файла конфигурации сервера.
    config = config_load()

    # Загрузка параметров командной строки, если нет параметров, то задаём
    # значения по умолчанию.
    listen_address, listen_port, gui_flag = arg_parser(
        config['SETTINGS']['Default_port'], config['SETTINGS']['Listen_Address'])

    # Инициализация базы данных.
    database = ServerStorage(
        os.path.join(
            config['SETTINGS']['Database_path'],
            config['SETTINGS']['Database_file']))

    # Создание экземпляра класса - сервера и его запуск:
    server = MessageProcessor(listen_address, listen_port, database)
    server.daemon = True
    server.start()

    # Если указан параметр без GUI, то запускаем простенький обработчик
    # консольного ввода
    if gui_flag:
        while True:
            command = input('Введите exit для завершения работы сервера.')
            if command == 'exit':
                # Если выход, то завышаем основной цикл сервера.
                server.running = False
                server.join()
                break

    # Если не указан запуск без GUI, то запускаем GUI:
    else:
        # Создаём графическое окружение для сервера:
        server_app = QApplication(sys.argv)
        server_app.setAttribute(Qt.AA_DisableWindowContextHelpButton)
        main_window = MainWindow(database, server, config)

        # Запускаем GUI
        server_app.exec_()

        # По закрытию окон останавливаем обработчик сообщений.
        server.running = False


if __name__ == '__main__':
    main()
