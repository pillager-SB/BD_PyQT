import json
import sys

sys.path.append('../')
from common.variables import *
from common.decor import log


@log
def get_message(sock):
    """
    Функция принимает и декодирует сообщение.
    Принимает байты, возвращает словарь,
    при несоответствии данных отдает ошибку значения.
    """

    encoded_response = sock.recv(MAX_PACKAGE_LENGTH)
    if isinstance(encoded_response, bytes):
        json_response = encoded_response.decode(ENCODING)
        response = json.loads(json_response)
        if isinstance(response, dict):
            return response
        else:
            raise TypeError


@log
def send_message(sock, message):
    """
    Функция отправки словарей через сокет.
    Функция принимает словарь, извлекает из него строку,
    строку кодирует в байты и отправляет.
    """
    js_message = json.dumps(message)
    encoded_message = js_message.encode(ENCODING)
    sock.send(encoded_message)
