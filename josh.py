from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.utils.markdown import hbold
from aiogram.dispatcher.filters.state import State, StatesGroup
import pymysql.cursors
from datetime import datetime
from config import BOT_TOKEN, ADMIN_ID, OUTPUT_CHAT, DB_NAME, HOST, PORT, USER, PASSWORD, DEFAULT_PARSE_MODE

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())


async def send_output(admin_answer, user_id, username, link_to_chat=None):
    if link_to_chat is not None:
        date = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        text = f"🕠 {hbold('Время')} - {date}\n✉️ {hbold('Ответ модератора')}: {admin_answer}\n🧟 {hbold('Пользователь')}: @{username} | {user_id}"
        await bot.send_message(chat_id=link_to_chat, text=text, parse_mode=DEFAULT_PARSE_MODE)


def connect(db_name=None):
    try:
        connection_ = pymysql.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=PASSWORD,
            database=db_name,
            cursorclass=pymysql.cursors.DictCursor
        )

        print("Connection Successful")
        return connection_
    except Exception as err:
        print("Connection was failed")
        print(err)


class States(StatesGroup):
    change_name = State()
    change_chat_link = State()
    change_support_link = State()
    change_info_channel_link = State()
    send_application = State()


connection = connect(DB_NAME)
cursor = connection.cursor()


def get_admin_keyboard(add_back_button: bool = False):
    keyboard_ = InlineKeyboardMarkup(row_width=2, inline_keyboard=[
        [
            InlineKeyboardButton(text=f"⬜ Изменить название проекта", callback_data="change_name"),
            InlineKeyboardButton(text=f"⬜ Изменить ссылку на чат", callback_data="change_chat_link")
        ],
        [
            InlineKeyboardButton(text=f"⬜ Изменить ссылку на поддежку", callback_data="change_support_link"),
            InlineKeyboardButton(text=f"⬜ Изменить ссылку на инфо-канал", callback_data="change_info_channel_link")
        ],
    ])

    if add_back_button:
        keyboard_.add(InlineKeyboardButton(text=f"🔙 Назад", callback_data="back"))

    return keyboard_

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    if cursor.execute(f"SELECT * FROM `users` WHERE user_id = {message.from_user.id};") == 0:
        cursor.execute(f"INSERT INTO `users`(user_id, username, already_send) VALUES (%s, %s, %s);",
                       (message.from_user.id, message.from_user.username, False))
        cursor.execute(f"SELECT * FROM `project` WHERE creator_id={ADMIN_ID}")
        project_data = dict(cursor.fetchone())
        cursor.execute(
            f"UPDATE `project` SET total_users = {project_data['total_users'] + 1} WHERE creator_id={ADMIN_ID}")
        connection.commit()

    cursor.execute(f"SELECT * FROM `project` WHERE creator_id={ADMIN_ID}")
    project_data = dict(cursor.fetchone())

    if message.from_user.id != ADMIN_ID:
        keyboard_user = ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, keyboard=[
            [KeyboardButton("Подать заявку")]
        ])
        await message.reply(
            f"Добро пожаловать в {hbold(project_data['project_name'])}!!!\n\nДля подачи заявки нажмите на кнопку {hbold('`Подать заявку`')}\n\nCreator: @dkhodos",
            reply_markup=keyboard_user, parse_mode=DEFAULT_PARSE_MODE)
    else:
        keyboard_user = ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, keyboard=[
            [KeyboardButton("Показать статистику")]
        ])
        await message.reply(f"{hbold('Добро пожаловать!!!')}\n\nCreator: @dkhodos", reply_markup=keyboard_user, parse_mode=DEFAULT_PARSE_MODE)


@dp.message_handler(text="Подать заявку")
async def send_application(message: types.Message):
    cursor.execute(f"SELECT * FROM `users` WHERE user_id = {message.from_user.id}")
    user = dict(cursor.fetchone())
    if user["already_send"]:
        await message.reply(text=f"⛔ {hbold('Вы уже подавали заявку.')}", parse_mode=DEFAULT_PARSE_MODE)
    else:
        text = f"Напишите:\n\n{hbold('1.Ссылку на форум')}\n{hbold('2.Опыт работы')}\n{hbold('3.Кол-во времени, которые вы будете уделять работе')}"
        await message.reply(text=text, parse_mode=DEFAULT_PARSE_MODE)
        await States.send_application.set()


@dp.message_handler(text="Показать статистику")
async def show_statistics(message: types.Message):
    cursor.execute(f"SELECT * FROM `project` WHERE creator_id = {message.from_user.id}")
    project_data = dict(cursor.fetchone())

    text = f"📈 Статистика по {hbold(project_data['project_name'])}:\n\n🧟 {hbold('Пользователей')}: {project_data['total_users']}\n✅ {hbold('Принятых пользователей')}: {project_data['accepted_users']}\n⏰ {hbold('Пользователей ожидающих подтверждения')}: {project_data['pending_users']}\n❌ {hbold('Не принятых пользователей')}: {project_data['declined_users']}\n"
    await message.reply(text=text, parse_mode=DEFAULT_PARSE_MODE)


@dp.message_handler(state=States.send_application)
async def send_application_state(message: types.Message, state: FSMContext):
    await state.update_data(user_answer=message.text)
    data = await state.get_data()
    user_answer = data["user_answer"]
    cursor.execute(f"UPDATE `users` SET already_send = True WHERE user_id={message.from_user.id}")
    connection.commit()
    cursor.execute(f"SELECT * FROM `project` WHERE creator_id={ADMIN_ID}")
    project_data = dict(cursor.fetchone())
    cursor.execute(
        f"UPDATE `project` SET pending_users = {project_data['pending_users'] + 1} WHERE creator_id={ADMIN_ID}")
    connection.commit()
    await message.reply(text=f"⏰ {hbold('Ваша заявка была отправлена на рассмотрение.')}", parse_mode=DEFAULT_PARSE_MODE)
    text = f"🔔 {hbold('Новая заявка!')} @{message.from_user.username} | {hbold(message.from_user.id)}\n\n{hbold('Текст')}:\n{user_answer}"
    keyboard_admin = InlineKeyboardMarkup(row_width=2, inline_keyboard=[
        [
            InlineKeyboardButton(f"✅ Принять", callback_data=f"accept_application_{message.from_user.id}"),
            InlineKeyboardButton(f"❌ Отказать", callback_data=f"decline_application_{message.from_user.id}")
        ]
    ])
    await bot.send_message(chat_id=ADMIN_ID, text=text, reply_markup=keyboard_admin, parse_mode=DEFAULT_PARSE_MODE)
    await state.finish()


@dp.callback_query_handler(text_contains="accept_application")
async def accept_applcation(callback_data: types.CallbackQuery):
    _, _, user_id = callback_data.data.split("_")

    cursor.execute(f"SELECT * FROM `project` WHERE creator_id = {ADMIN_ID};")
    project_data = dict(cursor.fetchone())
    keywords = {
        "chat_link": f"💫 Чат",
        "support_link": f"📱 Саппорт",
        "info_channel_link": f"📰 Инфо-Канал",
    }
    keyboard_result = InlineKeyboardMarkup(row_width=1, inline_keyboard=[
        [InlineKeyboardButton(text=keywords[key], url=project_data[key])] for key in project_data if
        project_data[key] is not None if "link" in key
    ])
    cursor.execute(
        f"UPDATE `project` SET pending_users = {project_data['pending_users'] - 1} WHERE creator_id = {ADMIN_ID}")
    cursor.execute(
        f"UPDATE `project` SET accepted_users = {project_data['accepted_users'] + 1} WHERE creator_id = {ADMIN_ID}")
    connection.commit()
    await bot.send_message(chat_id=user_id, text=f"🌟 {hbold('Ваша заявка была принята!')}",
                           reply_markup=keyboard_result, parse_mode=DEFAULT_PARSE_MODE)
    await callback_data.message.delete()

    cursor.execute(f"SELECT * FROM `users` WHERE user_id = {user_id}")
    user_data = dict(cursor.fetchone())
    await send_output(f"✔️ {hbold('Принято')}", user_id, user_data["username"], OUTPUT_CHAT)


@dp.callback_query_handler(text_contains="decline_application")
async def decline_application(callback_data: types.CallbackQuery):
    _, _, user_id = callback_data.data.split("_")
    cursor.execute(f"SELECT * FROM `project` WHERE creator_id = {ADMIN_ID};")
    project_data = dict(cursor.fetchone())
    cursor.execute(
        f"UPDATE `project` SET pending_users = {project_data['pending_users'] - 1} WHERE creator_id = {ADMIN_ID}")
    cursor.execute(
        f"UPDATE `project` SET declined_users = {project_data['declined_users'] + 1} WHERE creator_id = {ADMIN_ID}")
    connection.commit()
    await bot.send_message(chat_id=user_id, text="⛔ Ваша заявка была отклонена", parse_mode=DEFAULT_PARSE_MODE)
    await callback_data.message.delete()

    cursor.execute(f"SELECT * FROM `users` WHERE user_id = {user_id}")
    user_data = dict(cursor.fetchone())
    await send_output(f"⛔ {hbold('Откзано')}", user_id, user_data["username"], OUTPUT_CHAT)


@dp.message_handler(commands=["settings"])
async def settings(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply(f"⛔ {hbold('Данная команда недоступна')}")
    else:
        if cursor.execute(f"SELECT * FROM `project` WHERE creator_id = {message.from_user.id};") == 0:
            await message.reply(text=f"💤 {hbold('Иницилизирую проект')}", parse_mode=DEFAULT_PARSE_MODE)
            cursor.execute(
                "INSERT INTO `project`(creator_id, total_users, pending_users, declined_users, accepted_users) VALUES (%s, %s, %s, %s, %s);",
                (message.from_user.id, 0, 0, 0, 0))
            connection.commit()
        cursor.execute(f"SELECT * FROM `project` WHERE creator_id = {message.from_user.id};")
        project = dict(cursor.fetchone())
        text = f"💻 {hbold('Настройки')}:\n\n⬜ {hbold('Название проекта')}: " \
               f"{project['project_name'] if project['project_name'] is not None else 'Не установлено'}\n" \
               f"⬜ {hbold('Ссылка на чат')}: {project['chat_link'] if project['chat_link'] is not None else 'Не установлено'}\n" \
               f"⬜ {hbold('Ссылка на поддержку')}: {project['support_link'] if project['support_link'] is not None else 'Не установлено'}\n" \
               f"⬜ {hbold('Ссылка на инфо-канал')}: {project['info_channel_link'] if project['info_channel_link'] is not None else 'Не установлено'}\n"

        await message.reply(text=text, reply_markup=get_admin_keyboard(), parse_mode=DEFAULT_PARSE_MODE)


@dp.callback_query_handler(text="change_name")
async def change_name(callback_data: types.CallbackQuery):
    await callback_data.message.edit_text(f"⬜ {hbold('Укажите новое название')}:", parse_mode=DEFAULT_PARSE_MODE)

    await States.change_name.set()


@dp.message_handler(state=States.change_name)
async def change_name_state(message: types.Message, state: FSMContext):
    await state.update_data(new_name=message.text)
    data = await state.get_data()
    new_name = data["new_name"]

    cursor.execute(f"UPDATE `project` SET project_name = '{new_name}' WHERE creator_id = {message.from_user.id};")
    # cursor.execute(
    connection.commit()
    text = f"✅ {hbold('Новое название было установлено')}: {new_name}"
    await message.reply(text=text, reply_markup=get_admin_keyboard(True), parse_mode=DEFAULT_PARSE_MODE)
    await state.finish()


@dp.callback_query_handler(text="change_chat_link")
async def change_chat_link(callback_data: types.CallbackQuery):
    await callback_data.message.edit_text(f"⬜ {hbold('Укажите новую ссылку на чат')}:", parse_mode=DEFAULT_PARSE_MODE)

    await States.change_chat_link.set()


@dp.message_handler(state=States.change_chat_link)
async def change_chat_link_state(message: types.Message, state: FSMContext):
    await state.update_data(new_chat_link=message.text)
    data = await state.get_data()
    new_chat_link = data["new_chat_link"]

    cursor.execute(f"UPDATE `project` SET chat_link = '{new_chat_link}' WHERE creator_id = {message.from_user.id};")
    connection.commit()
    text = f"✅ {hbold('Новая ссылка на чат была установлена')}: {new_chat_link}"
    await message.reply(text=text, reply_markup=get_admin_keyboard(True), parse_mode=DEFAULT_PARSE_MODE)
    await state.finish()




@dp.message_handler(state=States.change_support_link)
async def change_name_state(message: types.Message, state: FSMContext):
    await state.update_data(new_support_link=message.text)
    data = await state.get_data()
    new_support_link = data["new_support_link"]

    cursor.execute(
        f"UPDATE `project` SET support_link = '{new_support_link}' WHERE creator_id = {message.from_user.id};")
    connection.commit()
    text = f"✅ {hbold('Новое название было установлено')}: {new_support_link}"
    await message.reply(text=text, reply_markup=get_admin_keyboard(True), parse_mode=DEFAULT_PARSE_MODE)
    await state.finish()


@dp.callback_query_handler(text="change_info_channel_link")
async def change_name(callback_data: types.CallbackQuery):
    await callback_data.message.edit_text(f"⬜ {hbold('Укажите новую ссылку на инфо-канал')}:", parse_mode=DEFAULT_PARSE_MODE)

    await States.change_info_channel_link.set()


@dp.message_handler(state=States.change_info_channel_link)
async def change_name_state(message: types.Message, state: FSMContext):
    await state.update_data(new_info_channel_link=message.text)
    data = await state.get_data()
    new_info_channel_link = data["new_info_channel_link"]

    cursor.execute(
        f"UPDATE `project` SET info_channel_link = '{new_info_channel_link}' WHERE creator_id = {message.from_user.id};")
    connection.commit()
    text = f"✅ {hbold('Новое название было установлено')}: {new_info_channel_link}"
    await message.reply(text=text, reply_markup=get_admin_keyboard(True), parse_mode=DEFAULT_PARSE_MODE)
    await state.finish()



if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
