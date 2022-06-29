import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
file_handler_log = logging.FileHandler(os.path.basename(__file__) + '.log',
                                       encoding="utf-8")
formater = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler_log.setFormatter(formater)
file_handler_log.setLevel(logging.INFO)
logger.addHandler(file_handler_log)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formater)
stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logger.info('Начинаем попытку отправки ссобщения в telegram')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Успешно отправили сообщение в telegram "{message}"')
    except telegram.error.Unauthorized:
        raise exceptions.TelegramError('Unauthorized')
    except telegram.error.BadRequest:
        raise exceptions.TelegramError('BadRequest')
    except telegram.error.TimedOut:
        raise exceptions.TelegramError('TimedOut')
    except telegram.error.NetworkError:
        raise exceptions.TelegramError('NetworkError')
    except telegram.error.ChatMigrated:
        raise exceptions.TelegramError('ChatMigrated')
    except telegram.error.TelegramError:
        raise exceptions.TelegramError('TelegramError')
    except Exception as error:
        raise exceptions.TelegramError(error)


def get_api_answer(current_timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    logger.info(f'Начинаем запрос к яндекс эндпоинт {ENDPOINT} с параметрами '
                '{params}')
    try:
        homework_statuses = requests.get(ENDPOINT, headers=headers,
                                         params=params)
    except requests.exceptions.ConnectionError:
        raise exceptions.YandexError(
            'Ошибка соединения с Яндекс эндпоинт ошибка ConnectionError, '
            'параметры {params}')
    except Exception as error:
        raise exceptions.YandexError(
            f'Ошибка соединения с Яндекс эндпоинт {error}, параметры {params}')
    if homework_statuses.status_code != 200:
        raise exceptions.YandexError(
            f'Яндекс эндпоинт вернул код {homework_statuses.status_code}, '
            'параметры {params}')
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict) or not response:
        raise exceptions.YandexTypeError('Некорректный ответ от яндекс '
                                         'эндпоинт "{response}"')
    if not response.get('current_date'):
        raise exceptions.YandexTypeError('В ответе яндекс эндпоинт '
                                         'отсутствует обязательный ключ '
                                         'current_date')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise exceptions.YandexTypeError('В ответе яндекс эндпоинт '
                                         'отсутствует обязательный ключ '
                                         'homeworks или тип ключа '
                                         'некорректный')
    return homeworks


def parse_status(homework):
    """Информации о конкретной домашней работе и статус этой работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise exceptions.YandexKeyError(f'В работе {homework} отсутствует '
                                        'обязательный ключ homework_name')
    homework_status = homework.get('status')
    verdict = VERDICTS.get(homework_status)
    if not verdict:
        raise exceptions.YandexKeyError(f'В работе {homework_name} неизвестный'
                                        ' статус {homework_status}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проеверка переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def write_in_log_error(error, last_error, bot):
    """Записывает в лог ошибку."""
    logger.error(error)
    if bot and error != last_error:
        send_message(bot, error)
    current_timestamp = int(time.time())
    return current_timestamp


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = ('Отсутствуют обязательные переменные окружения во '
                         'времязапуска бота!')
        logger.critical(error_message)
        sys.exit(error_message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_error = ''
    error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_timestamp = response.get('current_date'), int(time.time())
            if not homeworks:
                logger.debug('Статусы работ не изменились')
            else:
                message = parse_status(homeworks[0])
                send_message(bot, message)
        except exceptions.YandexError as yandex_error:
            error = yandex_error
            current_timestamp = write_in_log_error(error, last_error, bot)
        except exceptions.YandexKeyError as yandex_error:
            error = yandex_error
            current_timestamp = write_in_log_error(error, last_error, bot)
        except exceptions.YandexTypeError as yandex_error:
            error = yandex_error
            current_timestamp = write_in_log_error(error, last_error, bot)
        except exceptions.TelegramError as telegram_error:
            error = f'Сбой в работе Telegram: {telegram_error}'
            current_timestamp = write_in_log_error(error, last_error, False)
        except Exception as unknown_error:
            error = f'Сбой в работе программы: {unknown_error}'
            current_timestamp = write_in_log_error(error, last_error, bot)
        else:
            logger.debug('Не возникло исключений')
        finally:
            time.sleep(RETRY_TIME)
            last_error = error
            error = ''


if __name__ == '__main__':
    main()
