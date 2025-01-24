import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import Database
from bot.models.employees import Employee

logger = logging.getLogger(__name__)
router = Router()

async def is_employee(message: Message) -> bool:
    if not message.from_user:
        return False
    telegram_id_str = str(message.from_user.id)

    db_sess = Database.get_session()
    try:
        emp = db_sess.query(Employee).filter(Employee.user_id == telegram_id_str).first()
        return emp is not None
    finally:
        db_sess.close()

@router.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для работы с календарём.\n"
        "Команды:\n"
        "/add <user_id> — добавить сотрудника\n"
        "/rm <user_id> — удалить сотрудника\n"
    )

@router.message(Command(commands=["add"]))
async def cmd_add(message: Message):
    if not await is_employee(message):
        await message.answer("Вы не являетесь сотрудником. Доступ запрещен.")
        return

    args = message.text.strip().split()
    if len(args) < 2:
        await message.answer("Укажите Telegram user_id: /add <user_id>")
        return

    numeric_id_str = args[1]

    db_sess = Database.get_session()
    try:
        existing = db_sess.query(Employee).filter(Employee.user_id == numeric_id_str).first()
        if existing:
            await message.answer(f"Сотрудник с user_id={numeric_id_str} уже есть в базе.")
        else:
            new_emp = Employee(user_id=numeric_id_str, username="")
            db_sess.add(new_emp)
            db_sess.commit()
            await message.answer(f"Сотрудник c user_id={numeric_id_str} добавлен!")
    finally:
        db_sess.close()

@router.message(Command(commands=["rm"]))
async def cmd_remove(message: Message):
    if not await is_employee(message):
        await message.answer("Вы не являетесь сотрудником. Доступ запрещен.")
        return

    args = message.text.strip().split()
    if len(args) < 2:
        await message.answer("Укажите Telegram user_id: /rm <user_id>")
        return

    numeric_id_str = args[1]

    db_sess = Database.get_session()
    try:
        emp = db_sess.query(Employee).filter(Employee.user_id == numeric_id_str).first()
        if not emp:
            await message.answer(f"Сотрудник с user_id={numeric_id_str} не найден.")
        else:
            db_sess.delete(emp)
            db_sess.commit()
            await message.answer(f"Сотрудник с user_id={numeric_id_str} удалён!")
    finally:
        db_sess.close()
