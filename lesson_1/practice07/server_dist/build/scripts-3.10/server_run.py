import sys
import os


def main():
    PYTHON_PATH = sys.executable
    file_path = os.getcwd() + '/server.py'
    print(f'{PYTHON_PATH} {file_path}')
    os.system(f'{PYTHON_PATH} {file_path}')


if __name__ == '__main__':
    main()
