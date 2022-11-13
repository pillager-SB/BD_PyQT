import inspect
import logging
import sys
from functools import wraps

sys.path.append('../')
import logs.config_client_log
import logs.config_server_log

class Log:
    def __init__(self, logger=None):
        self.logger = logger

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            parent_func_name = inspect.currentframe().f_back.f_code.co_name
            sep_sym = ["/", "\\"]['win' in sys.platform]  # Определяю разделитель под используемую ОС(Win/Linux)
            module_name = inspect.currentframe().f_back.f_code.co_filename.split(sep_sym)[-1]
            if not self.logger:  # Если logger не получил имени модуля явным образом, значит это
                # не 'client' и не 'server'.
                logger_name = module_name.split('.')[0]
                self.logger = logging.getLogger(logger_name)
            self.logger.debug(f'функция {func.__name__} вызвана из функции {parent_func_name} '
                              f'в модуле {module_name} с аргументами: {args}; {kwargs if kwargs else ""}')
            result = func(*args, **kwargs)
            return result

        return wrapper
