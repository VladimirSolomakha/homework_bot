import logging
import os
import time

from dotenv import load_dotenv

import exceptions

import requests

import telegram

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

logger = logging.getLogger(__name__)
file_handler_log = logging.FileHandler(os.path.basename(__file__) + '.log',
                                       'a', "utf-8")
formater = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler_log.setFormatter(formater)
file_handler_log.setLevel(logging.INFO)
logger.addHandler(file_handler_log)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
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
    try:
        homework_statuses = requests.get(ENDPOINT, headers=headers,
                                         params=params)
    except requests.exceptions.ConnectionError:
        raise exceptions.YandexError(
            'Ошибка соединения с Яндекс эндпоинт ConnectionError')
    except Exception as error:
        raise exceptions.YandexError(
            f'Ошибка соединения с Яндекс эндпоинт {error}')
    if homework_statuses.status_code != 200:
        raise exceptions.YandexError(
            f'Яндекс эндпоинт вернул код {homework_statuses.status_code}')
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not type(response) == dict or not response:
        raise TypeError
    homeworks = response.get('homeworks')
    if type(homeworks) != list:
        raise TypeError
    if not homeworks:
        logger.debug('Статусы работ не изменились')
    return homeworks


def parse_status(homework):
    """Информации о конкретной домашней работе и статус этой работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    if not verdict:
        raise KeyError
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проеверка переменных окружения."""
    if not PRACTICUM_TOKEN:
        return False
    if not TELEGRAM_TOKEN:
        return False
    if not TELEGRAM_CHAT_ID:
        return False
    return True


def write_in_log_error(error, last_error, bot):
    """Записывает в лог ошибку."""
    logger.error(error)
    if bot and error != last_error:
        send_message(bot, error)
    current_timestamp = int(time.time())
    time.sleep(RETRY_TIME)
    return current_timestamp


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(
            'Отсутствуют обязательные переменные'
            'окружения во времязапуска бота!'
        )
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_error = ''
    error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)
                logger.info(message)
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except exceptions.YandexError as ya_error:
            error = str(ya_error)
            current_timestamp = write_in_log_error(error, last_error, bot)
        except KeyError:
            error = 'Некорректный статус работы!'
            current_timestamp = write_in_log_error(error, last_error, bot)
        except TypeError:
            error = 'Некорректный ответ от api яндекс!'
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
            last_error = error
            error = ''


if __name__ == '__main__':
    main()
