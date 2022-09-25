import logging
import os
import requests
import sys
import telegram
import time

from dotenv import load_dotenv
from exceptions import APIErrException
from http import HTTPStatus

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s %(name)s %(levelname)s  %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.ERROR
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def send_message(bot, message):
    """Отправляем сообщение в телеграмм бот."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение отправлено')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения: {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params
                                         )
    except Exception as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
        raise Exception(f'Ошибка при запросе к основному API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        logging.error(f'Ошибка {status_code}')
        raise Exception(f'Ошибка {status_code}')
    try:
        return homework_statuses.json()
    except ValueError:
        logger.error('Ошибка парсинга ответа из формата json')
        raise ValueError('Ошибка парсинга ответа из формата json')


def check_response(response):
    """проверяет ответ API на корректность."""
    if type(response) is not dict:
        raise TypeError('Ответ API отличен от словаря')
    try:
        list_works = response['homeworks']
    except KeyError:
        logger.error('Ошибка словаря по ключу homeworks')
        raise KeyError('Ошибка словаря по ключу homeworks')
    try:
        homework = list_works[0]
    except IndexError:
        logger.error('Список домашних работ пуст')
        raise IndexError('Список домашних работ пуст')
    return homework


def parse_status(homework):
    """извлекает статус работы."""
    if 'homework_name' in homework:
        homework_name = homework.get('homework_name')
    else:
        msg = 'API вернул домашнее задание без ключа "homework_name" key'
        raise KeyError(msg)
    homework_status = homework.get('status')
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except KeyError:
        msg = ('API вернулось'
               f'неизвестный статус {homework_status} for "{homework_name}"'
               )
        raise APIErrException(msg)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """проверяет доступность переменных окружения."""
    return all(
        [
            TELEGRAM_TOKEN,
            PRACTICUM_TOKEN,
            TELEGRAM_CHAT_ID,
        ]
    )


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical("Отсутствует переменная окружения")
        return 0
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    STATUS = ''
    ERROR_CACHE_MESSAGE = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            message = parse_status(check_response(response))
            if message != STATUS:
                send_message(bot, message)
                STATUS = message
            time.sleep(RETRY_TIME)
        except Exception as error:
            logger.error(error)
            message_t = str(error)
            if message_t != ERROR_CACHE_MESSAGE:
                send_message(bot, message_t)
                ERROR_CACHE_MESSAGE = message_t
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
