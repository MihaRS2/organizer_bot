import logging
from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.db import Database
from bot.models.events import Event
from bot.models.employees import Employee
import pytz

logger = logging.getLogger(__name__)
router = Router()

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

async def is_employee_by_callback(callback: CallbackQuery) -> bool:
    """
    Проверяем, есть ли callback.from_user.id (числовой) в employees.user_id.
    """
    if not callback.from_user:
        return False
    telegram_id_str = str(callback.from_user.id)

    db_sess = Database.get_session()
    try:
        emp = db_sess.query(Employee).filter_by(user_id=telegram_id_str).first()
        return emp is not None
    finally:
        db_sess.close()

@router.callback_query(lambda c: c.data and c.data.startswith("take:"))
async def handle_take_meeting(callback: CallbackQuery):
    logger.debug("User %s tries to TAKE meeting, data=%s", callback.from_user.username, callback.data)

    if not await is_employee_by_callback(callback):
        await callback.message.edit_text("Вы не являетесь сотрудником. Доступ запрещен.")
        await callback.answer()
        return

    event_id = callback.data.split(":")[1]
    db_sess = Database.get_session()
    try:
        event = db_sess.query(Event).filter(Event.event_id == event_id).first()
        if not event:
            await callback.message.edit_text("Встреча не найдена в базе.")
        else:
            if event.is_taken:
                await callback.message.edit_text(f"Встреча уже взята @{event.taken_by}.")
            else:
                # Если пересекается с планёркой, не даём взять:
                # (На всякий случай повторная проверка, вдруг кнопка появилась)
                start_msk = event.start_time.astimezone(MOSCOW_TZ)
                end_msk = event.end_time.astimezone(MOSCOW_TZ)

                # Простая локальная функция
                def is_overlap_with_support_planning(local_start, local_end):
                    def intervals_overlap(s1, e1, s2, e2):
                        return s1 < e2 and s2 < e1
                    wd = local_start.weekday()
                    # Понедельник=0 (15:00-16:00), Пятница=4 (15:00-17:00)
                    if wd == 0:
                        plan_s = local_start.replace(hour=15, minute=0, second=0)
                        plan_e = local_start.replace(hour=16, minute=0, second=0)
                        return intervals_overlap(local_start, local_end, plan_s, plan_e)
                    elif wd == 4:
                        plan_s = local_start.replace(hour=15, minute=0, second=0)
                        plan_e = local_start.replace(hour=17, minute=0, second=0)
                        return intervals_overlap(local_start, local_end, plan_s, plan_e)
                    return False

                if is_overlap_with_support_planning(start_msk, end_msk):
                    await callback.message.edit_text(
                        "‼️ Внимание встреча пересекается с планеркой отдела тех.поддержки,\n"
                        "нельзя взять эту встречу!"
                    )
                else:
                    event.is_taken = True
                    event.taken_by = (
                        callback.from_user.username.lower()
                        if callback.from_user.username
                        else f"user_id_{callback.from_user.id}"
                    )
                    db_sess.commit()

                    decline_btn = InlineKeyboardButton(
                        text="Отказаться от встречи",
                        callback_data=f"decline:{event_id}"
                    )
                    markup = InlineKeyboardMarkup(inline_keyboard=[[decline_btn]])

                    start_str = start_msk.strftime("%H:%M")
                    end_str = end_msk.strftime("%H:%M")

                    await callback.message.edit_text(
                        f"Встреча: {event.title}\n"
                        f"Время: {start_str} - {end_str}\n"
                        f"Взял(а): @{callback.from_user.username or callback.from_user.id}",
                        reply_markup=markup
                    )
        await callback.answer()
    finally:
        db_sess.close()

@router.callback_query(lambda c: c.data and c.data.startswith("decline:"))
async def handle_decline_meeting(callback: CallbackQuery):
    logger.debug("User %s tries to DECLINE meeting, data=%s", callback.from_user.username, callback.data)

    if not await is_employee_by_callback(callback):
        await callback.message.edit_text("Вы не являетесь сотрудником. Доступ запрещен.")
        await callback.answer()
        return

    event_id = callback.data.split(":")[1]
    db_sess = Database.get_session()
    try:
        event = db_sess.query(Event).filter(Event.event_id == event_id).first()
        if not event:
            await callback.message.edit_text("Встреча не найдена.")
        else:
            current_user_lower = (
                callback.from_user.username.lower()
                if callback.from_user.username
                else f"user_id_{callback.from_user.id}"
            )
            if event.is_taken and event.taken_by == current_user_lower:
                event.is_taken = False
                event.taken_by = None
                db_sess.commit()

                take_btn = InlineKeyboardButton(
                    text="Взять встречу",
                    callback_data=f"take:{event_id}"
                )
                markup = InlineKeyboardMarkup(inline_keyboard=[[take_btn]])

                start_str = event.start_time.astimezone(MOSCOW_TZ).strftime("%H:%M")
                end_str = event.end_time.astimezone(MOSCOW_TZ).strftime("%H:%M")

                await callback.message.edit_text(
                    f"Встреча: {event.title}\n"
                    f"Время: {start_str} - {end_str}\n"
                    "Встреча снова доступна для взятия.",
                    reply_markup=markup
                )
            else:
                # Если пользователь не ответственен — показываем alert вместо затирания сообщения.
                await callback.answer("Вы не являетесь ответственным за эту встречу.", show_alert=True)
                return
        await callback.answer()
    finally:
        db_sess.close()
