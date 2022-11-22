import datetime
import os
import sys

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker
from common.variables import SERVER_DATABASE

sys.path.append(os.path.join(os.getcwd(), '..'))


# Класс серверной базы данных.
class ServerStorage:
    Base = declarative_base()

    # Таблица 1. Данные пользователей
    class AllUsers(Base):
        __tablename__ = 'users'
        id = Column(Integer, primary_key=True)
        name = Column(String, unique=True)
        last_login = Column(DateTime(timezone=True))

        def __init__(self, name):
            self.name = name
            self.last_login = datetime.datetime.now()

        def __repr__(self):
            return "<User(%s, %s)>" % (self.name, self.last_login)

    # Таблица A. Активные пользователи.
    # Добавил из соображений, что такая информация будет полезна для работы мессенджера.
    class ActiveUsers(Base):
        __tablename__ = 'active_users'
        id = Column(Integer, primary_key=True)
        user = Column(ForeignKey('users.id'), unique=True)
        ip_address = Column(String)
        port = Column(Integer)
        login_time = Column(DateTime(timezone=True), server_default=func.now())

        def __init__(self, user, ip, port):
            self.user = user
            self.ip_address = ip
            self.port = port

        def __repr__(self):
            return "<User('%s','%s', '%s', '%s')>" % (self.user, self.ipaddress, self.port, self.login_time)

    class LoginHistory(Base):
        __tablename__ = 'login_history'
        id = Column(Integer, primary_key=True)
        user = Column(ForeignKey('users.id'))
        ip_address = Column(String)
        port = Column(Integer)
        date_time = Column(DateTime(timezone=True), server_default=func.now())

        def __init__(self, user, ip, port):
            self.user = user
            self.ip_address = ip
            self.port = port

        def __repr__(self):
            return "<User('%s','%s', '%s', '%s')>" % (self.user, self.ipaddress, self.port, self.date_time)

    def __init__(self):
        self.engine = create_engine(SERVER_DATABASE,
                                    echo=False,
                                    pool_recycle=7200,
                                    connect_args={'check_same_thread': False})

        self.Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Предварительная очистка таблицы активных пользователей.
        self.session.query(self.ActiveUsers).delete()
        self.session.commit()

    def user_login(self, username, ip_address, port):
        """
        Функция выполняется при входе пользователя, записывает в базу факт входа.
        :param username:
        :param ip_address:
        :param port:
        :return:
        """
        resp = self.session.query(self.AllUsers).filter_by(name=username)
        if resp.count():
            user = resp.first()
            user.last_login = datetime.datetime.now()
        else:
            # Add new user
            user = self.AllUsers(username)
            self.session.add(user)
        self.session.commit()
        # Далее создаю запись в таблицу активных пользователей о факте входа:
        new_active_user = self.ActiveUsers(user.id, ip_address, port)
        self.session.add(new_active_user)
        # Далее создаю запись в таблицу login_history:
        history = self.LoginHistory(user.id, ip_address, port)
        self.session.add(history)
        self.session.commit()

    def user_logout(self, username):
        """
        Функция фиксирует факт отключения пользователя.
        Удаляет его запись из активных пользователей.
        :param username:
        :return:
        """
        user = self.session.query(self.AllUsers).filter_by(name=username).first()
        # Убираю уходящего из таблицы активных пользователей.
        self.session.query(self.ActiveUsers).filter_by(user=user.id).delete()
        self.session.commit()

    def users_list(self):
        """
        Функция запрашивает записи из таблицы пользователей.
        :return: Список кортежей из известных пользователей со временем последнего входа.
        """
        users = self.session.query(self.AllUsers.name, self.AllUsers.last_login)
        return users.all()

    def active_users_list(self):
        """
        Функция запрашивает данные из таблиц AllUsers и ActiveUsers.
        :return: Список кортежей активных пользователей(имя, ip-адрес, порт, время подключения)
        """
        users = self.session.query(
            self.AllUsers.name,
            self.ActiveUsers.ip_address,
            self.ActiveUsers.port,
            self.ActiveUsers.login_time
        ).join(self.AllUsers)

        return users.all()

    def login_history(self, username=None):
        """
        Функция запрашивает историю входа по username/all
        :param username:
        :return:
        """
        query = self.session.query(
            self.AllUsers.name,
            self.LoginHistory.ip_address,
            self.LoginHistory.port,
            self.LoginHistory.date_time,
        ).join(self.AllUsers)

        if username:
            query = query.filter(self.AllUsers.name == username)
        return query.all()


if __name__ == '__main__':
    test_db = ServerStorage()
    test_db.user_login('Clinet 1', '192.168.0.1', 8080)
    test_db.user_login('Clinet 2', '192.168.0.2', 8081)

    print(test_db.active_users_list())
    print(test_db.login_history())

    test_db.user_logout('Clinet 1')

    print(test_db.active_users_list())
    print(test_db.login_history())

    print(test_db.users_list())
