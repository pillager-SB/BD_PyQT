from ipaddress import ip_address, IPv4Address, AddressValueError
from socket import gethostbyname, gaierror
from subprocess import Popen, PIPE
from tabulate import tabulate
import sys


def host_ping(addresses_lst, timeout=100, requests=1):
    """
    host_ping() - функция, проверяющая доступность сетевых узлов.
    :param addresses_lst: Список ip-адресов и/или имен хостов.
    :param timeout: Время ожидания ответа (100).
    :param requests: Количество запросов (1).
    :return: Словарь со списками результатов проверки.
    """
    result = {"Узел доступен": [], "Узел недоступен": []}
    for address in addresses_lst:
        try:
            _ = ip_address(address)  # Проверка элемента списка на соответствие IP4/IP6 адресу.
        except ValueError:  # Сюда попадут предположительно хостнеймы.
            try:
                address = gethostbyname(address)  # Пытаюсь получить ip-адрес из host name.
            except gaierror:  # В случае неудачи вывожу сообщение в консоль.
                print(f'Attention! Address "{address}" is not valid!', file=sys.stderr)
        prc = Popen(f"ping {address} -w {timeout} -n {requests}", shell=False, stdout=PIPE)
        prc.wait()
        select = ['Узел доступен', 'Узел недоступен'][bool(prc.returncode)]  # Если вернулся 0 - доступен, иначе - нет.
        result[select].append(f'{str(address)}')  # Добавляю ip-адрес в соответствующий список.
        print(f'{address.ljust(15)} - {select}')  # Вывожу в консоль сообщение о доступности ip-адреса.

    print('+' + '-' * 37 + '+\n')  # Вывожу разделитель.
    return result


def host_range_ping():
    """
    host_range_ping() - функция, проверяющая доступность ip-адресов в диапазоне заданном пользователем.
    Важно! Функция работает только с IP4 адресами!
    :return: Передача списка адресов в host_ping().
    """
    while True:
        # Запрос у пользователя начального адреса.
        start_ip = input('Введите IP4-адрес: ')
        try:
            adr = IPv4Address(start_ip)
        except AddressValueError:
            continue
        last_oct = int(start_ip.split('.')[-1])  # Получаю число из последнего октета.
        break
    while True:
        # Запрос у пользователя количества проверяемых адресов.
        count_ip = input('Введите количество адресов для проверки: ')
        match count_ip.isnumeric():
            case 1:
                count_ip = int(count_ip)
                if (last_oct + count_ip) > 255:
                    print(f'Проверка возможна только в диапазоне последнего октета,\n'
                          f'число проверок для {adr} не может превышать: {255 - last_oct}')
                else:
                    break
    # Создаю список адресов, проверяю. Возвращаю словарь из host_ping().
    return host_ping([str(adr + n) for n in range(count_ip + 1)])


def host_range_ping_tab():
    """
    host_range_ping_tab() - функция, осуществляющая печать результатов работы host_ping() в "табличном" виде.
    :return:
    """
    request_dct = host_range_ping()

    print(f'Таблица доступности ip-адресов:',
          tabulate(request_dct, headers='keys', tablefmt='grid', stralign="center"),
          sep="\n")


if __name__ == '__main__':
    ip_addresses_lst = ['google.com', 'yandex.ru', '192.168.199.1', "kjlkjlk", 'localhost', '192.168.1.1']
    host_ping(ip_addresses_lst)
    host_range_ping()
    host_range_ping_tab()
