#! /usr/bin/env python3
# coding=utf-8

import requests
import logging
import json
from telegram.ext import Updater
from telegram.ext import CommandHandler, Filters, MessageHandler

CONFIG = {}


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

@msg_wrapper
def group(bot, update):
    """
        Handle messages from group
    """
    return bot.send_message(chat_id=update.message.chat_id, text=update.message.text)

@msg_wrapper
def user_id(bot, update):
    '''
        Handle `/user-id` command
    '''
    return bot.send_message(chat_id=update.message.chat_id, text=update.message.from_user.id)


def main():
    """
        Main function
    """
    read_config()
    updater = Updater(CONFIG['bot_token'])

    # Handle `/start`
    start_handler = CommandHandler('start', start)
    updater.dispatcher.add_handler(start_handler)

    # Handle `/user-id`
    updater.dispatcher.add_handler(CommandHandler('user_id', user_id))

    # Handle group message
    group_handler = MessageHandler(Filters.group, group)
    updater.dispatcher.add_handler(group_handler)

    updater.start_polling()

if __name__ == '__main__':
    # set logging
    logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s][%(name)s][%(pathname)s:%(lineno)s][%(levelname)s][%(message)s]')
    main()