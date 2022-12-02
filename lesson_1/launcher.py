"""Программа-лаунчер"""

import subprocess
import sys


def main():
    processes = []
    while True:
        action = input('Выберите действие: '
                       'q - выход, '
                       's - запустить сервер, '
                       'k - запустить клиенты, '
                       'x - закрыть все окна: ')

        match action:
            case 'q':
                break
            case 's':
                # Запуск сервера.
                processes.append(subprocess.Popen(f'{sys.executable} server.py',
                                                  creationflags=subprocess.CREATE_NEW_CONSOLE))
            case 'k':
                # Запуск клиентов.
                print('Убедитесь, что на сервере зарегистрировано необходимо количество клиентов с паролем 123456.')
                print('Первый запуск может быть достаточно долгим из-за генерации ключей!')
                clients = int(input('Введите количество клиентов для запуска: '))
                for i in range(clients):
                    processes.append(subprocess.Popen(f'{sys.executable} client.py -n test{i + 1} -p 123456',
                                                      creationflags=subprocess.CREATE_NEW_CONSOLE))
            case 'x':
                while processes:
                    processes.pop().kill()


if __name__ == '__main__':
    main()
