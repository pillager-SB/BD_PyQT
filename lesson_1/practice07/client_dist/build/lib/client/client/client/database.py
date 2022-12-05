import datetime
import os
from common.variables import *
from sqlalchemy import create_engine, Table, Column, Integer, String, DateTime, Text, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker


# Класс - база данных клиента.
class ClientDatabase:
    Base = declarative_base()

    class KnownUsers(Base):
        """
        Класс - отображение таблицы известных пользователей.
        """
        __tablename__ = 'known_users'
        id = Column(Integer, primary_key=True)
        username = Column(String)

        def __init__(self, user):
            self.id = None
            self.username = user

    class MessageStat(Base):
        """
        Класс - отображение таблицы статистики сообщений.
        """
        __tablename__ = 'message_history'
        id = Column(Integer, primary_key=True)
        contact = Column(String)
        direction = Column(String)
        message = Column(Text)
        date = Column(DateTime)

        def __init__(self, contact, direction, message):
            self.id = None
            self.contact = contact
            self.direction = direction
            self.message = message
            self.date = datetime.datetime.now()

    class Contacts(Base):
        """
        Класс - отображение списка контактов.
        """
        __tablename__ = 'contacts'
        id = Column(Integer, primary_key=True)
        name = Column(String, unique=True)

        def __init__(self, contact):
            self.id = None
            self.name = contact

    # Конструктор класса:
    def __init__(self, name):
        path = os.getcwd()
        filename = f'client_{name}.db3'
        self.database_engine = create_engine(f'sqlite:///{os.path.join(path, filename)}',
                                             echo=False,
                                             pool_recycle=7200,
                                             connect_args={'check_same_thread': False})

        self.Base.metadata.create_all(self.database_engine)
        Session = sessionmaker(bind=self.database_engine)
        self.session = Session()

        # Необходимо очистить таблицу контактов, т.к. при запуске они подгружаются с сервера.
        self.session.query(self.Contacts).delete()
        self.session.commit()

    def add_contact(self, contact):
        """
        Метод добавления контактов.
        """
        if not self.session.query(self.Contacts).filter_by(name=contact).count():
            contact_row = self.Contacts(contact)
            self.session.add(contact_row)
            self.session.commit()

    def contacts_clear(self):
        """
        Метод очистки таблицы со списком контактов.
        """
        self.session.query(self.Contacts).delete()

    def del_contact(self, contact):
        """
        Метод удаления контакта.
        """
        self.session.query(self.Contacts).filter_by(name=contact).delete()

    def add_users(self, users_list):
        """
        Метод добавления известных пользователей.
        Пользователи получаются только с сервера, поэтому при каждом обращении таблица очищается.
        """
        self.session.query(self.KnownUsers).delete()
        for user in users_list:
            user_row = self.KnownUsers(user)
            self.session.add(user_row)
        self.session.commit()

    def save_message(self, contact, direction, message):
        """
        Метод сохраняющий сообщения.
        """
        message_row = self.MessageStat(contact, direction, message)
        self.session.add(message_row)
        self.session.commit()

    def get_contacts(self):
        """
        Метод возвращающий контакты.
        """
        return [contact[0] for contact in self.session.query(self.Contacts.name).all()]

    def get_users(self):
        """
        Метод возвращающий список известных пользователей.
        """
        return [user[0] for user in self.session.query(self.KnownUsers.username).all()]

    def check_user(self, user):
        """
        Метод-проверка есть ли пользователь в известных.
        """
        if self.session.query(self.KnownUsers).filter_by(username=user).count():
            return True
        else:
            return False

    def check_contact(self, contact):
        """
        Метод-проверка есть ли пользователь в контактах.
        """
        if self.session.query(self.Contacts).filter_by(name=contact).count():
            return True
        else:
            return False

    def get_history(self, contact):
        """
        Метод возвращающий историю переписки с определенным пользователем.
        """
        query = self.session.query(self.MessageStat).filter_by(contact=contact)
        return [(history_row.contact, history_row.direction, history_row.message, history_row.date)
                for history_row in query.all()]


# отладка

if __name__ == '__main__':
    test_db = ClientDatabase('test1')
    # for i in ['test3', 'test4', 'test5']:
    #     test_db.add_contact(i)
    # test_db.add_contact('test4')
    # test_db.add_users(['test1', 'test2', 'test3', 'test4', 'test5'])
    # test_db.save_message('test1', 'test2', f'Привет! я тестовое сообщение от {datetime.datetime.now()}!')
    # test_db.save_message('test2', 'test1', f'Привет! я другое тестовое сообщение от {datetime.datetime.now()}!')
    # print(test_db.get_contacts())
    # print(test_db.get_users())
    # print(test_db.check_user('test1'))
    # print(test_db.check_user('test10'))
    # print(test_db.get_history('test2'))
    # print(test_db.get_history(contact='test2'), "direction")
    # print(test_db.get_history(contact='test1'), "direction")
    print(sorted(test_db.get_history('test2'), key=lambda item: item[3]))
    # print(test_db.get_history('test3'))
    # test_db.del_contact('test4')
    # print(test_db.get_contacts())
