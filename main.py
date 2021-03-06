#! /usr/bin/env python3
# coding=utf-8

import sys
import os
import logging
import json
import importlib
import time
import datetime
import requests
from telegram.ext import Updater
from telegram.ext import CommandHandler, Filters, MessageHandler
import telegram
from bs4 import BeautifulSoup
from tinydb import TinyDB, Query
import pytz

Daemon = importlib.import_module('daemon')

CONFIG = {}
DB = ''

def read_config():
    """
        Read config from `config.json`
    """
    global CONFIG
    with open("config.json", "r") as file:
        CONFIG = json.load(file)

    logging.debug("CONFIG: %s" % CONFIG)


def msg_wrapper(func):
    def wrapper(*args, **kwargs):
        update = args[1]
        logging_msg = "Receiving message from %d. Context: %s" % \
            (update.message.from_user.id, update.message.text)
        logging.info(logging_msg)
        # Check authorization
        user_id = update.message.from_user.id
        if str(user_id) not in CONFIG['admin']:
            logging_msg = "Non-admin user."
            logging.info(logging_msg)
            return
        # Call handler
        sent_msg = func(*args, **kwargs)
        logging_msg = 'Sent message: %s' % sent_msg.text
        logging.info(logging_msg)

    return wrapper


@msg_wrapper
def start(bot, update):
    """
        Handle `/start` command
    """
    return bot.send_message(chat_id=update.message.chat_id, text="I'm a bot, please talk to me!")


def user_id(bot, update):
    '''
        Handle `/user-id` command
    '''
    return bot.send_message(chat_id=update.message.chat_id, text=update.message.from_user.id)


@msg_wrapper
def get_kancolle_twitter_avatar(bot, update):
    '''
        Get the avatar of official Twitter account for Kantai Collection
    '''
    html = requests.get('https://twitter.com/KanColle_STAFF')
    soup = BeautifulSoup(html.text, "html.parser")
    tag = soup.find_all("a", class_="ProfileAvatar-container")
    image_url = str(tag[0]['data-resolved-url-large'])

    head = requests.head(image_url)
    last_modified_time_str = 'Unknown'
    if 'last-modified' in head.headers:
        last_modified_time_str = head.headers['last-modified']
        last_modified_time = datetime.datetime.strptime(last_modified_time_str, "%a, %d %b %Y %H:%M:%S %Z")
        last_modified_time = last_modified_time.replace(tzinfo=pytz.utc)
        last_modified_time_local = last_modified_time.astimezone()
        last_modified_time_japan = last_modified_time.astimezone(tz=pytz.timezone('Japan'))

    return_text = 'Avatar: %s\nLast modified GMT: %s' % (image_url, last_modified_time_str)
    if last_modified_time_str != 'Unknown':
        return_text += '\nServer time: %s\nJapan time: %s\n' % \
            (last_modified_time_local.strftime("%a, %d %b %Y %H:%M:%S %Z"), \
             last_modified_time_japan.strftime("%a, %d %b %Y %H:%M:%S %Z"))

    return bot.send_message(chat_id=update.message.chat_id, \
                text=return_text)


@msg_wrapper
def db_status(bot, update):
    '''
        Handle `/db_status` command
    '''
    db_name = "db-default.json"
    if 'db_name' in CONFIG:
        db_name = CONFIG['db_name']
    response_msg = 'Database name: %s\nDatabase file size: %s\nLast modified time: %s'\
         % (db_name, os.path.getsize(db_name), time.strftime("%d %b %Y %H:%M:%S", time.localtime(os.path.getmtime(db_name))))
    return bot.send_message(chat_id=update.message.chat_id, \
                text=response_msg)


@msg_wrapper
def imgur_upload(bot, update):
    '''
        Handle `/imgur_upload` command
    '''
    for key in ('imgur_client_refresh_token', 'imgur_client_id', 'imgur_client_secret'):
        if key not in CONFIG:
            return bot.send_message(chat_id=update.message.chat_id, text='No %s in config' % key)
    
    commands = update.message.text.split(' ')
    logging_msg = 'Commands: %s' % commands
    logging.info(logging_msg)
    if len(commands) != 2:
        return bot.send_message(chat_id=update.message.chat_id,  \
                text='Usage:\n`/imgur_upload URL`', parse_mode='Markdown')

    response = requests.post('https://api.imgur.com/oauth2/token', \
        data={
            'refresh_token': CONFIG['imgur_client_refresh_token'],
            'client_id': CONFIG['imgur_client_id'],
            'client_secret': CONFIG['imgur_client_secret'],
            'grant_type': 'refresh_token'
        })
    logging_msg = 'Response:\n%s' % response.text
    logging.info(logging_msg)
    access_token = json.loads(response.text)['access_token']

    response = requests.post('https://api.imgur.com/3/image', data={
        'image': commands[1]
    }, headers={
        'Authorization': 'Bearer %s' % access_token
    })
    logging_msg = 'Response:\n%s' % response.text
    logging.info(logging_msg)
    response_json = json.loads(response.text)

    try:
        if response_json['success'] == 'false':
            return bot.send_message(chat_id=update.message.chat_id, text=response_json['data']['error'])

        return bot.send_message(chat_id=update.message.chat_id, text=response_json['data']['link'])
    except KeyError:
        return bot.send_message(chat_id=update.message.chat_id, text='Error while parsing response.')


def error_callback(bot, update, error):
    try:
        raise error
    except telegram.error.Unauthorized:
        # remove update.message.chat_id from conversation list
        logging.error('Unauthorized')
    except telegram.error.BadRequest:
        # handle malformed requests - read more below!
        logging.error('BadRequest')
    except telegram.error.TimedOut:
        # handle slow connection problems
        logging.error('TimedOut')
    except telegram.error.NetworkError:
        # handle other connection problems
        logging.error('NetworkError')
    except telegram.error.ChatMigrated as e:
        # the chat_id of a group has changed, use e.new_chat_id instead
        logging.error('ChatMigrated')
    except telegram.error.TelegramError:
        # handle all other telegram related errors
        logging.error('TelegramError')


def main():
    """
        Main function
    """
    read_config()
    db_name = "db-default.json"
    if 'db_name' in CONFIG:
        db_name = CONFIG['db_name']
    DB = TinyDB(db_name)

    updater = Updater(CONFIG['bot_token'])

    # Handle `/start`
    start_handler = CommandHandler('start', start)
    updater.dispatcher.add_handler(start_handler)

    # Handle `/user_id`
    updater.dispatcher.add_handler(CommandHandler('user_id', user_id))
    # Handle `/kancolle_avatar`
    updater.dispatcher.add_handler(CommandHandler('kancolle_avatar', get_kancolle_twitter_avatar))
    # Handle `/db_status`
    updater.dispatcher.add_handler(CommandHandler('db_status', db_status))
    # Handle `/imgur_upload`
    updater.dispatcher.add_handler(CommandHandler('imgur_upload', imgur_upload))

    # Register error handler
    updater.dispatcher.add_error_handler(error_callback)

    updater.start_polling()

class BotDaemon(Daemon.Daemon):
    def run(self):
        main()


usage = 'main.py {start|status|restart|stop}'
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(usage)
        exit(0)
    
    debug = False
    if len(sys.argv) == 3 and sys.argv[2] == '-d':
        debug = True
    
    # set logging
    if debug:
        logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s][%(name)s][%(pathname)s:%(lineno)s][%(levelname)s][%(message)s]')
        logging.info('Debug mode.')
    else:
        logging.basicConfig(level=logging.ERROR,
                    format='[%(asctime)s][%(name)s][%(pathname)s:%(lineno)s][%(levelname)s][%(message)s]')
    # Daemon
    daemon = BotDaemon('/tmp/tg_bot_0x590F_test.pid', stderr='bot-err.log')

    operation = sys.argv[1]
    if operation == "status":
        print("Viewing daemon status")
        pid = daemon.get_pid()

        if not pid:
            print("Daemon isn't running ;)")
        else:
            print("Daemon is running [PID=%d]" % pid)
    elif operation == "start":
        print('Starting bot...')
        daemon.start()
        pid = daemon.get_pid()

        if not pid:
            print("Unable run daemon")
        else:
            print("Daemon is running [PID=%d]" % pid)
    elif operation == 'stop':
        print("Stoping daemon")
        daemon.stop()
    elif operation == 'restart':
        print("Restarting daemon")
        daemon.restart()
    else:
        print(usage)
