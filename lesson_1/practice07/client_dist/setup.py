from setuptools import setup, find_packages

setup(name="my_mess_proj_client",
      version="0.0.1",
      description="my_mess_proj_client",
      author="Sergey Petin",
      author_email="pillager@bk.ru",
      packages=find_packages(),
      install_requires=['PyQt5', 'sqlalchemy', 'pycryptodomex']
      )
