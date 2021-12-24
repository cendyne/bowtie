import os
import traceback
import sys
import uuid
import time
import json
import logging
from typing import Dict, List, Text, Tuple, Union
from telegram.ext import Updater, InlineQueryHandler, CommandHandler, CallbackContext, ChatMemberHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import Update, InlineQueryResultCachedSticker, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from telegram.files.animation import Animation
from telegram.files.photosize import PhotoSize
from telegram.files.sticker import Sticker
from telegram.user import User

import bowtiedb

class Unbuffered(object):
    def __init__(self, stream):
        self.stream = stream
    def write(self, data):
        self.stream.write(data)
        self.stream.flush()
    def writelines(self, datas):
        self.stream.writelines(datas)
        self.stream.flush()
    def __getattr__(self, attr):
        return getattr(self.stream, attr)

sys.stdout = Unbuffered(sys.stdout)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


load_dotenv()

token = os.environ["BOT_TOKEN"]
downloads_path = os.environ["DOWNLOADS_PATH"]
admin = int(os.getenv("ADMIN"))

def downloadIconForUser(c: CallbackContext, user_id: int) -> Union[Text, None]:
    logging.info("Downloading icon for user %d", user_id)
    photos = c.bot.get_user_profile_photos(user_id, limit = 1)
    size = 0
    photo_to_use = None
    photo_id = None
    photo_ending = None
    if not photos is None:
        pictures = photos.photos
        if pictures and len(pictures) > 0:
            first_photo = pictures[0]
            if first_photo and len(first_photo):
                for photo in first_photo:
                    if photo.file_size > size:
                        photo_to_use = photo.file_id
                        photo_id = photo.file_unique_id
                        size = photo.file_size
    if photo_to_use:
        logging.info("Selected file size %d: %s", size, photo_to_use)
        photo_ending = "icon_" + photo_id + ".jpg"
        path = downloads_path + "/" + photo_ending
        if not os.path.exists(path):
            file = c.bot.get_file(photo_to_use)
            if not os.path.exists(downloads_path):
                os.makedirs(downloads_path)
            file.download(custom_path=path)
        return photo_ending
    return None

def downloadIconForChat(c: CallbackContext, chat_id: int) -> Union[Text, None]:
    logging.info("Downloading icon for chat %d", chat_id)
    chat = c.bot.get_chat(chat_id)
    photo = chat.photo
    photo_to_use = None
    photo_id = None
    photo_ending = None
    if photo:
        if photo.big_file_id:
            photo_to_use = photo.big_file_id
            photo_id = photo.big_file_unique_id
        elif photo.small_file_id:
            photo_to_use = photo.small_file_id
            photo_id = photo.small_file_unique_id
    if photo_to_use:
        logging.info("Selected file %s", photo_to_use)
        photo_ending = "icon_" + photo_id + ".jpg"
        path = downloads_path + "/" + photo_ending
        if not os.path.exists(path):
            file = c.bot.get_file(photo_to_use)
            if not os.path.exists(downloads_path):
                os.makedirs(downloads_path)
            file.download(custom_path=path)
        return photo_ending
    return None

def downloadPhoto(context: CallbackContext, photos: List[PhotoSize]) -> Union[Text, None]:
    size = 0
    photo_to_use = None
    photo_id = None
    photo_ending = None
    if photos and len(photos) > 0:
        for photo in photos:
            # logging.info("Photo %s", photo.to_json())
            if photo.file_size > size:
                photo_to_use = photo.file_id
                photo_id = photo.file_unique_id
                size = photo.file_size
    if photo_to_use:
        photo_ending = "photo_" + photo_id + ".jpg"
        path = downloads_path + "/" + photo_ending
        if not os.path.exists(path):
            file = context.bot.get_file(photo_to_use)
            if not os.path.exists(downloads_path):
                os.makedirs(downloads_path)
            file.download(custom_path=path)
            # TODO process photo
        return photo_ending
    return None

def downloadAnimation(context: CallbackContext, animation: Animation) -> Union[Text, None]:
    file_to_use = animation.file_id
    file_id = animation.file_unique_id
    if file_to_use:
        file_ending = "anim_" + file_id + ".mp4"
        path = downloads_path + "/" + file_ending
        if not os.path.exists(path):
            file = context.bot.get_file(file_to_use)
            if not os.path.exists(downloads_path):
                os.makedirs(downloads_path)
            file.download(custom_path=path)
        return file_ending
    return None

def downloadSticker(c: CallbackContext, sticker: Sticker) -> Union[Text, None]:
    photo_to_use = None
    photo_id = None
    photo_ending = None
    if not sticker is None:
        if not sticker.is_animated:
            photo_to_use = sticker.file_id
            photo_id = sticker.file_unique_id
        # animated stickers unsupported
                    
    if photo_to_use:
        photo_ending = "sticker_" + photo_id + ".webp"
        path = downloads_path + "/" + photo_ending
        if not os.path.exists(path):
            file = c.bot.get_file(photo_to_use)
            if not os.path.exists(downloads_path):
                os.makedirs(downloads_path)
            file.download(custom_path=path)
            # TODO process photo
        return photo_ending
    return None

def allowedUser(user: User) -> bool:
    if user and user.id == admin:
        return True
    # TODO dynamic permissions?
    return False

@bowtiedb.with_cursor
def textHandler(update: Update, context: CallbackContext) -> None:
    if not allowedUser(update.message.from_user):
        print("Unrecognized user %s", update.message.from_user)
        update.message.reply_text("401")
        return
    # print("Update %s", update)
    user = update.message.from_user
    if update.message.forward_from:
        user = update.message.forward_from
    chat = None
    if update.message.forward_from_chat:
        chat = update.message.forward_from_chat
    elif update.message.sender_chat:
        chat = update.message.sender_chat 
    if chat:
        icon = downloadIconForChat(context, chat.id)
        first_name = chat.title
    else:
        icon = downloadIconForUser(context, user.id)
        first_name = user.first_name
    entities = []
    text = update.message.text
    if update.message.entities:
        for entity in update.message.entities:
            entities.append(bowtiedb.TelegramMessageEntity(entity.type, entity.offset, entity.length, entity.url))
    entry = bowtiedb.Entry(int(time.time()), text, None, entities, first_name, icon)
    bowtiedb.add_entry(entry)

def photoHandler(update: Update, context: CallbackContext) -> None:
    if not allowedUser(update.message.from_user):
        update.message.reply_text("401")
        return
    user = update.message.from_user
    if update.message.forward_from:
        user = update.message.forward_from
    chat = None
    if update.message.forward_from_chat:
        chat = update.message.forward_from_chat
    elif update.message.sender_chat:
        chat = update.message.sender_chat 
    # print("Update %s", update)
    photo = downloadPhoto(context, update.message.photo)
    if photo:
        if chat:
            icon = downloadIconForChat(context, chat.id)
            first_name = chat.title
        else:
            icon = downloadIconForUser(context, user.id)
            first_name = user.first_name
        entities = []
        text = update.message.caption
        if update.message.caption_entities:
            for entity in update.message.caption_entities:
                entities.append(bowtiedb.TelegramMessageEntity(entity.type, entity.offset, entity.length, entity.url))
        entry = bowtiedb.Entry(int(time.time()), text, photo, entities, first_name, icon)
        bowtiedb.add_entry(entry)

def stickerHandler(update: Update, context: CallbackContext) -> None:
    if not allowedUser(update.message.from_user):
        update.message.reply_text("401")
        return
    user = update.message.from_user
    if update.message.forward_from:
        user = update.message.forward_from
    chat = None
    if update.message.forward_from_chat:
        chat = update.message.forward_from_chat
    elif update.message.sender_chat:
        chat = update.message.sender_chat 
    # print("Update %s", update)
    sticker = downloadSticker(context, update.message.sticker)
    if sticker:
        if chat:
            icon = downloadIconForChat(context, chat.id)
            first_name = chat.title
        else:
            icon = downloadIconForUser(context, user.id)
            first_name = user.first_name
        entities = []
        text = update.message.caption
        if update.message.caption_entities:
            for entity in update.message.caption_entities:
                entities.append(bowtiedb.TelegramMessageEntity(entity.type, entity.offset, entity.length, entity.url))
        entry = bowtiedb.Entry(int(time.time()), text, sticker, entities, first_name, icon)
        bowtiedb.add_entry(entry)

def animationHandler(update: Update, context: CallbackContext) -> None:
    if not allowedUser(update.message.from_user):
        update.message.reply_text("401")
        return
    user = update.message.from_user
    if update.message.forward_from:
        user = update.message.forward_from
    chat = None
    if update.message.forward_from_chat:
        chat = update.message.forward_from_chat
    elif update.message.sender_chat:
        chat = update.message.sender_chat
    # print("Update %s", update)
    animation = update.message.animation
    if not animation or animation.file_size > 10_000_000:
        update.message.reply_text("Too big")
        return
    anim = downloadAnimation(context, animation)
    if anim:
        if chat:
            icon = downloadIconForChat(context, chat.id)
            first_name = chat.title
        else:
            icon = downloadIconForUser(context, user.id)
            first_name = user.first_name
        entities = []
        text = update.message.caption
        if update.message.caption_entities:
            for entity in update.message.caption_entities:
                entities.append(bowtiedb.TelegramMessageEntity(entity.type, entity.offset, entity.length, entity.url))
        entry = bowtiedb.Entry(int(time.time()), text, anim, entities, first_name, icon)
        bowtiedb.add_entry(entry)

def unsupportedHandler(update: Update, context: CallbackContext) -> None:
    if not allowedUser(update.message.from_user):
        update.message.reply_text("401")
        return
    update.message.reply_text("Unsupported")

def listHandler(update: Update, context: CallbackContext) -> None:
    print("Got list command")
    for entry in bowtiedb.find_entries():
        print("got entry " + str(entry))
        update.message.reply_text(entry.to_json())
        time.sleep(1)

def main() -> None:
    bowtiedb.init()
    # Create the Updater and pass it your bot's token.
    updater = Updater(token)

    # guestbookdb.set_config("username", updater.bot.username)
    print("Starting bot " + updater.bot.username)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("list", listHandler))

    # on non command i.e message - echo the message on Telegram
    dispatcher.add_handler(MessageHandler(Filters.sticker, stickerHandler))
    dispatcher.add_handler(MessageHandler(Filters.photo, photoHandler))
    dispatcher.add_handler(MessageHandler(Filters.text, textHandler))
    dispatcher.add_handler(MessageHandler(Filters.animation, animationHandler))
    dispatcher.add_handler(MessageHandler(Filters.all, unsupportedHandler))

    # for [id, name, file_id] in yelldb.findAllPending():
    #   updater.bot.send_document(
    #       chat_id=review_chan,
    #       document=file_id,
    #       reply_markup=InlineKeyboardMarkup([
    #          [InlineKeyboardButton(name, callback_data="YES " + id)],
    #          [InlineKeyboardButton("\u274C", callback_data="NO " + id)]
    #       ]))

    # Start the Bot
    updater.start_polling()

    # Block until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
