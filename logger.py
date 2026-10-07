import os
import var
from functools import lru_cache

@lru_cache
def get_log_file():
    if not os.path.exists('logs'):
        os.makedirs('logs')
    if os.path.exists('logs/log.log'):
        return 'logs/log.log'
    else:
        lnum = 1
        while True:
            if not os.path.exists(f'logs/log{lnum}.log'):
                return f'logs/log{lnum}.log'
            else:
                lnum += 1

var.log_file = get_log_file()

def write_log(message: str):
    with open(var.log_file, 'a', encoding='utf-8') as f:
        if not message.endswith('\n'):
            message = message + '\n'
        f.write(message)

def print_log(*message, **kwargs):
    print(*message, **kwargs)

@lru_cache
def color_str(message: str, color: str):
    return f"\033[{color}m{message}\033[0m"

def info(message):
    message = f"[INFO] {message}"
    write_log(message)
    print_log(color_str(message, '32'))

def warning(message):
    message = f"[WARNING] {message}"
    write_log(message)
    print_log(color_str(message, '33'))

def error(message):
    message = f"[ERROR] {message}"
    write_log(message)
    print_log(color_str(message, '31'))
