import json
import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = 712994870

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
url = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    filemode='w',
    encoding='utf-8'
)

# А тут установлены настройки логгера для текущего файла - example_for_log.py
logger = logging.getLogger(__name__)
# Устанавливаем уровень, с которого логи будут сохраняться в файл
logger.setLevel(logging.INFO)
# Указываем обработчик логов
handler = RotatingFileHandler(
    'program.log', maxBytes=50000000, backupCount=5)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    """Которые необходимы для работы программы."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.info('Отправляется запрос')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение успешно отправлено')
    except telegram.error.TelegramError as error:
        logging.error(error, exc_info=True)
        logging.debug(f'send_message {error}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        logging.info("Запрос к API")
        homework_statuses = requests.get(url, headers=HEADERS, params=payload)
        if homework_statuses.status_code != HTTPStatus.OK:
            logging.error('API домашки возвращает код, отличный от 200')
            raise requests.exceptions.HTTPError
        return homework_statuses.json()
    except json.JSONDecodeError as error:
        logging.error(f'Не удалось обработать JSON {error}')
        return None
    except requests.exceptions.RequestException as error:
        logging.error(f'запрос недоступен: {error}')
        raise KeyError
    except Exception:
        raise TypeError


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not response:
        logging.error('Нет ответа от сервера')
        raise Exception

    if not isinstance(response, dict):
        logging.error('Ответ API не словарь')
        raise TypeError

    if 'homeworks' not in response:
        logging.error('В ответе API нет ключа — список домашних работ')
        raise KeyError
    if not isinstance(response['homeworks'], list):
        logging.error('В ответе API домашние работы не список')
        raise TypeError
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус."""
    """Этой работы."""
    logging.debug('Начало парсинга')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if all([homework_name, homework_status]):
        verdict = HOMEWORK_VERDICTS.get(homework_status)
        if not verdict:
            raise ValueError(
                f'Недокументированный '
                f'статус домашней работы - {homework_status}')
    else:
        raise KeyError('В ответе API отсутствует имя работы или статус')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('нет  переменных окружения')
        raise SystemExit(-1)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp1 = 1
    timestamp2 = 0
    send_message(bot, 'Старт бота')
    while True:
        try:
            response = get_api_answer(timestamp1)
            homework = check_response(response)
            timestamp2 = response.get('current_date')
            if homework and timestamp1 != timestamp2:
                timestamp1 = timestamp2
                message = parse_status(homework[0])
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
