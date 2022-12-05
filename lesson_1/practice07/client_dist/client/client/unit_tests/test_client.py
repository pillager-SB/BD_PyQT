"""Unit-тесты клиента"""

import sys
import os
import unittest
sys.path.append(os.path.join(os.getcwd(), '..'))
from common.variables import RESPONSE, ERROR, USER, ACCOUNT_NAME, TIME, ACTION, PRESENCE
from client import create_presence, process_ans


class TestClass(unittest.TestCase):
    """Kлаcc с тестами"""

    def test_create_presence(self):
        """Тест корректного запроса"""
        test = create_presence()
        test[TIME] = 1665309507.8688447  # При работе программы параметр уникален, для проверки задаю
        # время константой (текущее время на момент написания дом. задания).
        self.assertEqual(test, {ACTION: PRESENCE, TIME: 1665309507.8688447, USER: {ACCOUNT_NAME: 'Guest'}})

    def test_200_ans(self):
        """Тест корректного разбора ответа 200"""
        self.assertEqual(process_ans({RESPONSE: 200}), '200 : Ok!')

    def test_type_200_ans(self):
        """Тест корректного типа данных для ответа 200"""
        self.assertTrue(isinstance(process_ans({RESPONSE: 200}), str), 'Возвращаемый тип данных не строка')
        #  Тест бессмысленный в плане проверки работоспособности конкретной функции,
        #  т.к. у нас будет строка в любом случае, но показывающий возможность проверки истинности выражений.

    def test_400_ans(self):
        """Тест корректного разбора 400"""
        self.assertEqual(process_ans({RESPONSE: 400, ERROR: 'Bad Request'}), '400 : Bad Request')

    def test_no_response(self):
        """Тест исключения без поля RESPONSE"""
        self.assertRaises(ValueError, process_ans, {ERROR: 'Bad Request'})


if __name__ == '__main__':
    unittest.main()
