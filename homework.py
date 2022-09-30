from http import HTTPStatus
import logging
import os
import time

from dotenv import load_dotenv
import requests
import telegram
from requests.exceptions import ConnectionError

from exceptions import APIErrException, EmptyAPIResponse, HTTPStatusError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, 'telegram_bot.log')

file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding=None)
stream_handler = logging.StreamHandler()

logging.basicConfig(
    format=('%(asctime)s, %(levelname)s, %(name)s,'
            '%(filename)s, %(funcName)s, %(lineno)d, %(message)s'),
    level=logging.INFO,
    handlers=[file_handler, stream_handler]
)


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram чат."""
    try:
        logging.info(f'Начата отправка сообщения в Телеграм {message}')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        user_username = bot.get_chat_member(
            TELEGRAM_CHAT_ID, TELEGRAM_CHAT_ID).user.username
        logging.info(
            f'Пользователю {user_username} отправлено сообщение: {message}'
        )
        return True

    except telegram.error.TelegramError as error:
        logging.error(f'Сообщение {message} не было отправлено')
        logging.error(f'Ошибка: {error}')
        return False


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': current_timestamp}
    query_dict = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': params,
    }
    try:
        logging.info(f"Проверка запроса к API: {'url'} {'headers'}"
                     f"{'params'}".format(**query_dict))
        response = requests.get(**query_dict)
        if response.status_code != HTTPStatus.OK:
            raise HTTPStatusError(
                f'Код ответа API: {response.status_code}'
                f'Причина: {response.reason}'
                f'Текст ошибки: {response.text}')
        return response.json()
    except ConnectionError as error:
        raise (f"Ошибка при запросе к основному API: {error} {'url'}"
               f"{'headers'} {'params'}".format(error, **query_dict))


def check_response(response):
    """проверяет ответ API на корректность."""
    logging.info('Получение домашних работ')
    if not isinstance(response, dict):
        raise TypeError('Ответ API отличен от словаря')
    if 'homeworks' not in response:
        raise APIErrException('Пустой ответ API')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise KeyError('Homeworks не список')
    return homeworks


def parse_status(homework):
    """Gets the status of a particular homework."""
    logging.info('Getting the status of a homework')
    if 'homework_name' not in homework:
        raise KeyError(
            'API вернул домашнее задание без ключа "homework_name" key')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError('Unknown status')
    if HOMEWORK_VERDICTS[homework_status] is None:
        raise KeyError('Unknown status')
    return (
        f'Изменился статус проверки работы "{homework_name}".'
        f'{HOMEWORK_VERDICTS[homework_status]}')


def check_tokens():
    """проверяет доступность переменных окружения."""
    no_tokens_msg = (
        'Программа принудительно остановлена. '
        'Отсутствует обязательная переменная окружения:')
    tokens_check = (
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
        ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID),
    )
    tokens_bool = True
    for tokens_name, tokens in tokens_check:
        if not tokens:
            logging.critical(
                f'{no_tokens_msg} {tokens_name}')
            tokens_bool = False
    return tokens_bool


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует переменная окружения'
                         'Программа принудительно остановлена')
        raise KeyError('Ошибка в ')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    prev_report = {}
    current_report = {}

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks_list = check_response(response)
            if homeworks_list:
                message = parse_status(homeworks_list[0])
                current_report['message'] = message
            else:
                current_report['message'] = 'Нет новых статусов'
            if current_report != prev_report:
                logging.info('Статус вашей домашней работы изменён')
                if send_message(bot, current_report['message']):
                    prev_report = current_report.copy()
                    current_timestamp = response.get(
                        "current_date",
                        current_timestamp
                    )
                else:
                    logging.info('Новых статусов нет')

        except EmptyAPIResponse as error:
            logging.info(f'Пустой ответ API. Ошибка: {error}')

        except Exception as error:
            logging.error(error)
            current_report['message'] = f'Произошёл сбой. Ошибка: {error}'
            if current_report != prev_report:
                send_message(bot, f'Произошёл сбой. Ошибка: {error}')
                prev_report = current_report.copy()
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
