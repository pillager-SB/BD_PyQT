"""Программа-лаунчер"""

import subprocess

PROCESSES = []

while True:
    ACTION = input('Выберите действие: '
                   'q - выход, '
                   's - запустить сервер и клиенты, '
                   'x - закрыть все окна: ')

    match ACTION:
        case 'q':
            break
        case 's':
            clients = int(input('Введите количество клиентов для запуска: '))
            # Запуск сервера.
            PROCESSES.append(subprocess.Popen('python server.py',
                                              creationflags=subprocess.CREATE_NEW_CONSOLE))
            # Запуск клиентов.
            for i in range(clients):
                PROCESSES.append(subprocess.Popen(f'python client.py -n test{i + 1}',
                                                  creationflags=subprocess.CREATE_NEW_CONSOLE))
        case 'x':
            while PROCESSES:
                PROCESSES.pop().kill()
