import dis


class ClientVerifier(type):

    def __init__(cls, clsname, bases, clsdict):

        methods = []  # Список методов, используемых в функциях класса LOAD_GLOBAL или LOAD_METHOD.
        for func in clsdict:
            try:
                ret = dis.get_instructions(clsdict[func])  # Проверяю, что функция.

            except TypeError:
                ...
            else:
                # Только в случае если все элементы - функции, разбираем используемые методы.
                for i in ret:

                    match i.opname:
                        case 'LOAD_GLOBAL':
                            if i.argval not in methods:
                                methods.append(i.argval)

        if any(i for i in ['accept', 'listen', 'socket'] if i in methods):
            raise TypeError('В классе обнаружено использование запрещённого метода!')

        if not any(i for i in ['get_message', 'send_message'] if i in methods):
            raise TypeError('Отсутствуют вызовы функций, работающих с сокетами.')

        super().__init__(clsname, bases, clsdict)



class ServerVerifier(type):

    def __init__(cls, clsname, bases, clsdict):
        methods = []  # Список методов, используемых в функциях класса (LOAD_GLOBAL, LOAD_METHOD).
        attrs = []  # Список аргументов (LOAD_ATTR).
        for func in clsdict:
            try:
                ret = dis.get_instructions(clsdict[func])  # Проверяю, что функция.
            except TypeError:
                ...
            else:
                # Только в случае если все элементы - функции, разбираем используемые методы.
                for i in ret:
                    match i:
                        case 'LOAD_GLOBAL' | 'LOAD_METHOD':
                            if i.argval not in methods:
                                methods.append(i.argval)
                        case 'LOAD_ATTR':
                            if i.argval not in attrs:
                                attrs.append(i.argval)

            if 'connect' in methods:
                raise TypeError('В серверном классе обнаружено использование запрещённого метода "connect"!')
            if not all(i for i in ['SOCK_STREAM', 'AF_INET'] if i in attrs):
                raise TypeError('Некорректная инициализация сокета.')

            super().__init__(clsname, bases, clsdict)
