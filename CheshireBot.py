import telebot
from random import randint
from os import environ
from BotEnv import *
import re

STATUS_MAP = {
    "read": Status.read,
    "trade": Status.trade,
    "admin": Status.admin
}

QUOTES = [
    "_If you don't know where you’re going, any road will take you there._",
    "_Oh, you can't help that. Most everyone's mad here. You may have noticed that I'm not all there myself._",
    "_I'm not crazy, my reality is just different than yours._",
    "_We're all mad here. Everyone in his own way._🐾",
    "_“Well, now that we have seen each other,” said the Unicorn, “if you'll believe in me, I'll believe in you. Is that a bargain?”_",
    "_How puzzling all these changes are! I'm never sure what I'm going to be, from one minute to another._",
    "_Imagination is the only weapon in the war against reality 😼._"
]

STICKERS = [
    "CAADAgADFAADl0dGExN2HmXbm5tVAg",
    "CAADAgADHwEAAgmmAgeO7F4AATZ2fxEC",
    "CAADAgADJQEAAgmmAgdeGaTzuc0XEgI",
    "CAADAgADEgIAAgmmAgfHPBCOsxwM7gI",
    "CAADAgADDwADl0dGE-S-Q0CLQEo-Ag"
]

MASTER_USER = int(environ["MASTER_USER"])
bot = telebot.TeleBot(environ["BOT_TOKEN"])
bot_env = BotEnv()


# @bot.message_handler(func=lambda message: True, content_types=['text', 'sticker'])
# def rofl_handler(message):
#     print(message)
#
#     if message.chat.type in ("supergroup", "group", "channel") and message.from_user.username == "ololo":
#         bot.send_sticker(message.chat.id, STICKERS[randint(0, 4)], message.message_id)

def get_chat_name(message):
    return message.chat.title if message.chat.title is not None else message.chat.username


def has_admin_privileges(message):
    user_id = message.from_user.id
    return user_id == MASTER_USER or bot_env.get_user_status(user_id) == Status.admin


def is_chat_trigger(message):
    chat = message.chat.id
    trigger = message.text
    return chat in bot_env.triggers and trigger in bot_env.triggers[chat] and not bot_env.triggers[chat][trigger].erased


def get_command_param(command_string, separator):
    parts = command_string.strip().split(separator)
    if len(parts) == 2:
        return parts[1]
    else:
        return None


def get_command_param_re(command, command_string):
    pattern = re.compile(r"^/" + command + " (.*)$")
    match = pattern.match(command_string)
    param = match.group(1)

    return param


def get_broadcast_handler(msg):
    handler = None
    message = None

    if msg.content_type == "photo":
        message = msg.photo[0].file_id
        handler = bot.send_photo
    elif msg.content_type == "text":
        message = msg.text
        handler = bot.send_message
    elif msg.content_type == "sticker":
        message = msg.sticker.file_id
        handler = bot.send_message

    return handler, message


def save_trigger(msg, chat_id, trigger_name):
    message = None

    if msg.content_type == "photo":
        message = msg.photo[0].file_id
    elif msg.content_type == "text":
        message = msg.text
    elif msg.content_type == "sticker":
        message = msg.sticker.file_id

    bot_env.triggers[chat_id][trigger_name] = Trigger(msg.content_type, message)


def del_trigger(chat_id, trigger_name):
    bot_env.triggers[chat_id][trigger_name].erased = True


@bot.message_handler(commands=['help'], func=lambda message: message.chat.type == "private")
def process_help_command(message):
    bot.send_message(message.chat.id,
                     "Cheshire help:\n"
                     "/orders - fetch list of your active orders.\n"
                     "/get_status - get status of target user")


@bot.message_handler(commands=['ping'])
def process_ping_command(message):
    bot.send_message(message.chat.id, QUOTES[randint(0, 6)], parse_mode='Markdown')


@bot.message_handler(commands=['broadcast'], func=has_admin_privileges)
def process_broadcast_command(message):
    replied_msg = message.reply_to_message
    if replied_msg is not None:
        handler, msg = get_broadcast_handler(replied_msg)
        for chat in bot_env.triggers.keys():
            handler(chat, msg)
    else:
        bot.send_message(message.chat.id, "Can't broadcast msg. Reply this command to target msg.")


@bot.message_handler(commands=['add_trigger'], func=has_admin_privileges)
def process_add_trigger_command(message):
    replied_msg = message.reply_to_message
    if replied_msg is not None:
        param = get_command_param_re('add_trigger', message.text)
        if param is not None:
            save_trigger(replied_msg, message.chat.id, param)
            bot.send_message(message.chat.id,
                             "Trigger '{}' was successfully saved for chat: '{}'".format(param, get_chat_name(message)))
        else:
            bot.send_message(message.chat.id,
                             "Improper add trigger format: '{}', trigger name should be delimited by space.".format(
                                 message.text))
    else:
        bot.send_message(message.chat.id, "Can't add trigger msg. Reply this command to target trigger msg.")


@bot.message_handler(commands=['del_trigger'], func=has_admin_privileges)
def process_del_trigger_command(message):
    param = get_command_param_re('del_trigger', message.text)
    if param is not None:
        if param in bot_env.triggers[message.chat.id]:
            del_trigger(message.chat.id, param)
            bot.send_message(message.chat.id, "Trigger '{}' was successfully deleted.".format(param))
        else:
            bot.send_message(message.chat.id,
                             "There is no trigger '{}' for chat '{}'.".format(param, get_chat_name(message)))
    else:
        bot.send_message(message.chat.id,
                         "Improper del trigger format: '{}', trigger name should be delimited by space.".format(
                             message.text))


@bot.message_handler(commands=['trigger_list'], func=has_admin_privileges)
def process_trigger_list_command(message):
    triggers = bot_env.get_chat_triggers(message.chat.id, get_chat_name(message))
    bot.send_message(message.chat.id, triggers)


@bot.message_handler(func=is_chat_trigger)
def process_trigger_command(message):
    callback = None
    chat_id = message.chat.id

    data = bot_env.triggers[chat_id][message.text]
    if data.type == "photo":
        callback = bot.send_photo
    elif data.type == "text":
        callback = bot.send_message
    elif data.type == "sticker":
        callback = bot.send_sticker

    callback(chat_id, data.msg)


@bot.message_handler(commands=['add_user'], func=has_admin_privileges)
def process_add_user_command(message):
    replied_msg = message.reply_to_message
    if replied_msg is not None:
        if not bot_env.user_exists(replied_msg.from_user.id):
            param = get_command_param(message.text, ' ')
            if param is not None and param in STATUS_MAP:
                status = STATUS_MAP[param]
            else:
                status = STATUS_MAP["read"]

            bot_env.add_user(replied_msg.from_user.id, replied_msg.from_user.username, status)
            bot.send_message(message.chat.id,
                             "User: @{} was successfully added with [{}] rights.".format(replied_msg.from_user.username,
                                                                                         status.name))
        else:
            bot.send_message(message.chat.id, "User: @{} is already exist.".format(replied_msg.from_user.username))
    else:
        bot.send_message(message.chat.id, "Can't identify user. Reply this command to target user msg.")


@bot.message_handler(commands=['dump'], func=has_admin_privileges)
def process_dump_command(message):
    bot_env.dump()
    bot.send_message(message.chat.id, "User data was successfully dumped into db.")


@bot.message_handler(commands=['set_status'], func=has_admin_privileges)
def process_set_status_command(message):
    replied_msg = message.reply_to_message
    if replied_msg is not None:
        if bot_env.user_exists(replied_msg.from_user.id) and message.text is not None:
            param = get_command_param(message.text, ' ')
            if param is not None and param in STATUS_MAP:
                bot_env.set_user_status(replied_msg.from_user.id, STATUS_MAP[param])
                bot.send_message(message.from_user.id,
                                 "@{0} status was successfully updated.".format(replied_msg.from_user.username))
            else:
                bot.send_message(message.from_user.id,
                                 "Wrong set_status format. Use:\n/set_status read".format(
                                     replied_msg.from_user.username))
        else:
            bot.send_message(message.from_user.id,
                             "Unknown user: @{} or invalid set_status message format".format(
                                 replied_msg.from_user.username))
    else:
        bot.send_message(message.from_user.id, "Can't identify user. Send this command as reply to target user msg.")


@bot.message_handler(commands=['get_status'], func=has_admin_privileges)
def process_get_status_command(message):
    if message.reply_to_message is not None:
        msg = message.reply_to_message
    else:
        msg = message

    if bot_env.user_exists(msg.from_user.id):
        info = bot_env.get_user_info(msg.from_user.id)
        bot.send_message(message.from_user.id, info)
    else:
        bot.send_message(message.from_user.id,
                         "User: @{} is not found in db.".format(msg.from_user.username))


@bot.message_handler(commands=['get_user_list'], func=has_admin_privileges)
def process_get_status_command(message):
    info = bot_env.get_all_user_info()
    bot.send_message(message.from_user.id, info)


@bot.message_handler(commands=['orders'], func=lambda message: message.chat.type == "private")
def process_orders_command(message):
    bot.send_message(message.chat.id, "You have no active orders for the moment.")


def main():
    print("Cheshire went for a walk.")
    bot.polling()
    print("Cheshire is home.")


if __name__ == '__main__':
    main()
