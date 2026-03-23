from typing import cast

from aiogram.types import KeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.common import ChangeUserRole, DeleteDomain, CloudFlareTokens, CloudFlareDeleteTokens
from app.states import CANCEL_TEXT


def change_role(roles) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in roles:
        builder.button(text='Change to {}'.format(item['new_role']), callback_data=ChangeUserRole(data='{}@{}'.format(item['id'], item['new_role'])).pack())
    builder.button(text='Cancel', callback_data=ChangeUserRole(data='canceled').pack())
    return cast(InlineKeyboardMarkup, builder.adjust(2).as_markup())


def remove_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    return cast(InlineKeyboardMarkup, builder.adjust(1).as_markup())


def delete_domain_inline(data) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='❌ delete {}'.format(data['domain']), callback_data=DeleteDomain(data='{}@{}'.format(data['id'], data['domain'].replace(':', ';'))).pack())
    builder.button(text='Cancel', callback_data=DeleteDomain(data='canceled').pack())
    return cast(InlineKeyboardMarkup, builder.adjust(1).as_markup())


def remove_cloudflare_token(ids: list) -> InlineKeyboardMarkup:
    builder_main = InlineKeyboardBuilder()
    for id in ids:
        builder_main.button(text=f'id: {id}', callback_data=CloudFlareTokens(id=str(id)).pack())

    builder_cancel = InlineKeyboardBuilder()
    builder_cancel.button(text='Cancel', callback_data=DeleteDomain(data='canceled').pack())

    main = cast(InlineKeyboardMarkup, builder_main.adjust(5).as_markup())
    cancel = cast(InlineKeyboardMarkup, builder_cancel.adjust(1).as_markup())

    main.inline_keyboard.append(cancel.inline_keyboard[0])

    return main

def confirmation_keyboard(id):
    builder = InlineKeyboardBuilder()
    builder.button(text='❌ Yes, delete this token', callback_data=CloudFlareDeleteTokens(id=str(id)).pack())
    builder.button(text='Cancel', callback_data=DeleteDomain(data='canceled').pack())
    return cast(InlineKeyboardMarkup, builder.adjust(1).as_markup())


def cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_reply_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
