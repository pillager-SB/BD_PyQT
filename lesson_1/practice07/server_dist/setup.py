#!usr/bin/env python
from setuptools import setup, find_packages

setup(name="my_mess_proj_server",
      version="0.0.6",
      description="my_mess_proj_server",
      author="Sergey Petin",
      author_email="pillager@bk.ru",
      packages=find_packages(),
      install_requires=['PyQt5', 'sqlalchemy', 'pycryptodomex'],
      #scripts=['server/server_run.py']
      )
