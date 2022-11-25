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

        #  Класс отображения таблицы контактов пользователей.
    class UsersContacts(Base):
        __tablename__ = 'contacts'
        id = Column(Integer, primary_key=True)
        user = Column(ForeignKey('users.id'))
        contact = Column(ForeignKey('users.id'))

        def __init__(self, user, contact):
            
            self.user = user
            self.contact = contact

        def __repr__(self):
            return "<UserContact('%s','%s')>" % (self.user, self.contact)

    # Класс отображения таблицы истории действий.
    class UsersHistory(Base):
        __tablename__ = 'user_history_table'
        id = Column(Integer, primary_key=True)
        user = Column(ForeignKey('users.id'))
        sent = Column(Integer)
        accepted = Column(Integer)

        def __init__(self, user):
            
            self.user = user
            self.sent = 0
            self.accepted = 0

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
        user_in_history = self.UsersHistory(user.id)
        self.session.add(user_in_history)

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
        users = self.session.query(self.AllUsers.name,
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

    def process_message(self, sender, recipient):
        """
        Функция фиксирует передачу сообщения и делает соответствующие отметки в БД
        :param sender:
        :param recipient:
        :return:
        """
        # Получаем ID отправителя sender и получателя recipient.
        sender = self.session.query(self.AllUsers).filter_by(name=sender).first().id
        recipient = self.session.query(self.AllUsers).filter_by(name=recipient).first().id
        # Запрашиваем строки из истории и увеличиваем счётчики
        sender_row = self.session.query(self.UsersHistory).filter_by(user=sender).first()
        sender_row.sent += 1
        recipient_row = self.session.query(self.UsersHistory).filter_by(user=recipient).first()
        recipient_row.accepted += 1

        self.session.commit()

    def add_contact(self, user, contact):
        """
        Функция добавляет контакт для пользователя.
        :param user:
        :param contact:
        :return:
        """
        # Получаем ID пользователей
        user = self.session.query(self.AllUsers).filter_by(name=user).first()
        contact = self.session.query(self.AllUsers).filter_by(name=contact).first()
        # Проверка на то, что пользователь существует или его еще нет в контактах юзера.
        if not contact or self.session.query(self.UsersContacts).filter_by(user=user.id,
                                                                           contact=contact.id).count():
            return

        # Создаём объект и заносим его в базу
        contact_row = self.UsersContacts(user.id, contact.id)
        self.session.add(contact_row)
        self.session.commit()

    def remove_contact(self, user, contact):
        """
        Функция удаляет контакт из базы данных.
        :param user:
        :param contact:
        :return:
        """
        # Получаем ID пользователей
        user = self.session.query(self.AllUsers).filter_by(name=user).first()
        contact = self.session.query(self.AllUsers).filter_by(name=contact).first()

        # Проверяю, что контакт существует.
        if not contact:
            return
        print(self.session.query(self.UsersContacts).filter(
            self.UsersContacts.user == user.id,
            self.UsersContacts.contact == contact.id
        ).delete())
        self.session.commit()

    def get_contacts(self, username):
        """
        Функция возвращает список контактов пользователя.
        :param username:
        :return:
        """
        # Запрашиваю указанного пользователя.
        user = self.session.query(self.AllUsers).filter_by(name=username).one()

        # Запрашиваю его список контактов.
        query = self.session.query(self.UsersContacts, self.AllUsers.name). \
            filter_by(user=user.id). \
            join(self.AllUsers, self.UsersContacts.contact == self.AllUsers.id)

        # выбираем только имена пользователей и возвращаем их.
        return [contact[1] for contact in query.all()]

    def message_history(self):
        """
        Функция возвращает количество переданных и полученных сообщений.
        :return:
        """
        query = self.session.query(
            self.AllUsers.name,
            self.AllUsers.last_login,
            self.UsersHistory.sent,
            self.UsersHistory.accepted
        ).join(self.AllUsers)
        # Возвращаем список кортежей
        return query.all()


if __name__ == '__main__':
    test_db = ServerStorage()
    test_db.user_login('Client 1', '192.168.0.1', 8080)
    test_db.user_login('Client 2', '192.168.0.2', 8081)
    print(test_db.users_list())
    print(test_db.active_users_list())
    # test_db.user_logout('Client 1')
    print(test_db.active_users_list())
    print(test_db.login_history('teta'))
    print(test_db.login_history('Client 1'))
    test_db.add_contact('Client 2', 'Client 1')
    # test_db.add_contact('test1', 'test3')
    # test_db.add_contact('test1', 'test6')
    # test_db.remove_contact('test1', 'test3')

    # test_db.process_message('Client 1', 'Hi!')
    # print(test_db.message_history())
