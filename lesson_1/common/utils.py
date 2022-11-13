import json
import sys

sys.path.append('../')
from errors import IncorrectDataReceivedError, NonDictInputError
from common.variables import MAX_PACKAGE_LENGTH, ENCODING
from decor import Log


@Log()
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
        raise IncorrectDataReceivedError
    raise IncorrectDataReceivedError


@Log()
def send_message(sock, message):
    """
    Функция принимает словарь, извлекает из него строку,
    строку кодирует в байты и отправляет.
    """
    if not isinstance(message, dict):
        raise NonDictInputError

    js_message = json.dumps(message)
    encoded_message = js_message.encode(ENCODING)
    sock.send(encoded_message)
