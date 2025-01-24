import asyncio
import logging
from datetime import datetime, timedelta
import pytz

from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import BotConfig
from bot.encryption import EncryptionManager
from bot.db import Database
from bot.caldav_client import CalDavClient
from bot.models.events import Event

from bot.handlers.commands import router as commands_router
from bot.handlers.callbacks import router as callbacks_router

logger = logging.getLogger(__name__)

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

TOLERANCE_SECONDS = 240  # 4 минуты

def times_differ_enough(dt_old: datetime, dt_new: datetime) -> bool:
    diff_sec = abs((dt_new - dt_old).total_seconds())
    return diff_sec >= TOLERANCE_SECONDS

def detect_if_technical(title: str) -> bool:
    keywords = [
        "тех.встреча",
        "тех. встреча",
        "техвстреча",
        "тех встреча",
        "технич. встреча",
        "техничиская встреча",
        "техническая встреча",
        "техническая",
        "technical meeting",
        "тех.вкс",
        "тех. вкс",
        "тех.созвон",
        "тех. созвон",
        "тех созвон",
        "[тех встреча]",
        "(тех встреча)",
        "техконсультация",
        "тех.консультация",
        "технические вопросы",
    ]
    lower_title = title.lower()
    return any(k in lower_title for k in keywords)

def is_overlap_with_support_planning(local_start: datetime, local_end: datetime) -> bool:
    """
    Проверяем пересечение с планёрками техподдержки:
      - Понедельник 15:00–16:00
      - Пятница     15:00–17:00
    """
    def intervals_overlap(s1, e1, s2, e2):
        return s1 < e2 and s2 < e1

    wd = local_start.weekday()  # 0=Пн, 4=Пт
    if wd == 0:
        plan_s = local_start.replace(hour=15, minute=0, second=0)
        plan_e = local_start.replace(hour=16, minute=0, second=0)
        return intervals_overlap(local_start, local_end, plan_s, plan_e)
    elif wd == 4:
        plan_s = local_start.replace(hour=15, minute=0, second=0)
        plan_e = local_start.replace(hour=17, minute=0, second=0)
        return intervals_overlap(local_start, local_end, plan_s, plan_e)
    return False

async def on_startup():
    logger.info("Bot startup initiated. Initializing Database...")
    Database.init()

def filter_today_events(raw_events, now_msk: datetime):
    today_date = now_msk.date()
    filtered = []
    for e in raw_events:
        local_start = pytz.UTC.localize(e["start"]).astimezone(MOSCOW_TZ)
        if local_start.date() == today_date:
            filtered.append(e)
    return filtered

def is_excluded_planerka(title: str) -> bool:
    """
    Проверяем, является ли событие планёркой:
      - Если title ровно "Support планёрка"
      - Или title ровно "Большая планерка"
    Тогда исключаем из любых оповещений
    """
    lower_t = title.lower().strip()
    return lower_t == "support планёрка" or lower_t == "большая планерка"

async def morning_today_events(bot: Bot):
    logger.debug("morning_today_events() called.")
    now_msk = datetime.now(MOSCOW_TZ)
    start_of_day_msk = datetime(now_msk.year, now_msk.month, now_msk.day, 0, 0, tzinfo=MOSCOW_TZ)
    end_of_day_msk = datetime(now_msk.year, now_msk.month, now_msk.day, 23, 59, tzinfo=MOSCOW_TZ)

    caldav_client = CalDavClient()
    raw_events = caldav_client.get_upcoming_events(start_of_day_msk, end_of_day_msk)
    events = filter_today_events(raw_events, now_msk)

    # Фильтруем планёрки, которые не хотим отправлять
    events = [ev for ev in events if not is_excluded_planerka(ev["title"])]

    logger.debug("Found %d events for today (morning), after exclusion.", len(events))
    if not events:
        msg_text = "Доброе утро!\nНа сегодня встреч нет (или только планёрки)."
        try:
            await bot.send_message(chat_id=BotConfig.SALES_CHAT_ID, text=msg_text)
        except Exception:
            logger.exception("Failed to send 'no events' message.")
        return

    greeting_text = f"Доброе утро!\nНа сегодня назначено {len(events)} встреч."
    try:
        await bot.send_message(chat_id=BotConfig.SALES_CHAT_ID, text=greeting_text)
    except Exception:
        logger.exception("Failed to send greeting message.")

    db_sess = Database.get_session()
    try:
        for e in events:
            existing = db_sess.query(Event).filter(Event.event_id == e["event_id"]).first()
            if not existing:
                new_ev = Event(
                    event_id=e["event_id"],
                    title=e["title"],
                    start_time=e["start"],
                    end_time=e["end"],
                    is_technical=detect_if_technical(e["title"])
                )
                db_sess.add(new_ev)
                db_sess.commit()

            local_start = pytz.UTC.localize(e["start"]).astimezone(MOSCOW_TZ)
            local_end = pytz.UTC.localize(e["end"]).astimezone(MOSCOW_TZ)
            start_str = local_start.strftime("%H:%M")
            end_str = local_end.strftime("%H:%M")

            text = (
                f"Встреча на сегодня!\n"
                f"{e['title']}\n"
                f"{start_str} - {end_str}"
            )

            # Если тех.встреча:
            if detect_if_technical(e["title"]):
                text += "\n‼️ Внимание это тех.встреча!!"

            overlap = is_overlap_with_support_planning(local_start, local_end)
            if overlap:
                text += "\n‼️ Внимание встреча пересекается с планеркой отдела тех.поддержки, перенесите встречу!!!"
                # Не показываем кнопку "Взять", т.к. пересекается
                markup = None
            else:
                # Добавляем кнопку
                take_btn = InlineKeyboardButton(
                    text="Взять встречу",
                    callback_data=f"take:{e['event_id']}"
                )
                markup = InlineKeyboardMarkup(inline_keyboard=[[take_btn]])

            try:
                if markup:
                    await bot.send_message(chat_id=BotConfig.SALES_CHAT_ID, text=text, reply_markup=markup)
                else:
                    await bot.send_message(chat_id=BotConfig.SALES_CHAT_ID, text=text)
            except Exception:
                logger.exception("Failed to send event message.")

        db_sess.commit()
    finally:
        db_sess.close()

async def check_for_updates(bot: Bot):
    logger.debug("check_for_updates() called.")
    now_msk = datetime.now(MOSCOW_TZ)
    if not (7 <= now_msk.hour < 20):
        logger.info("Outside of 7:00-20:00 range, skip updates.")
        return

    start_of_day_msk = datetime(now_msk.year, now_msk.month, now_msk.day, 0, 0, tzinfo=MOSCOW_TZ)
    end_of_day_msk = datetime(now_msk.year, now_msk.month, now_msk.day, 23, 59, tzinfo=MOSCOW_TZ)

    caldav_client = CalDavClient()
    raw_events = caldav_client.get_upcoming_events(start_of_day_msk, end_of_day_msk)
    events_today = filter_today_events(raw_events, now_msk)

    # Сразу отсекаем "Support планёрка" и "Большая планерка"
    events_today = [ev for ev in events_today if not is_excluded_planerka(ev["title"])]

    logger.debug("events_today after filter & exclusion: %d", len(events_today))

    current_ids = [ev["event_id"] for ev in events_today]
    db_sess = Database.get_session()
    try:
        for e in events_today:
            existing = db_sess.query(Event).filter(Event.event_id == e["event_id"]).first()
            if not existing:
                local_end = pytz.UTC.localize(e["end"]).astimezone(MOSCOW_TZ)
                if local_end > now_msk:
                    new_ev = Event(
                        event_id=e["event_id"],
                        title=e["title"],
                        start_time=e["start"],
                        end_time=e["end"],
                        is_technical=detect_if_technical(e["title"])
                    )
                    db_sess.add(new_ev)
                    db_sess.commit()

                    local_start = pytz.UTC.localize(e["start"]).astimezone(MOSCOW_TZ)
                    start_str = local_start.strftime("%H:%M")
                    end_str = local_end.strftime("%H:%M")

                    text = (
                        "‼️‼️ ВНИМАНИЕ! Встреча назначена день в день!\n"
                        f"{e['title']}\n"
                        f"{start_str} - {end_str}"
                    )
                    if detect_if_technical(e["title"]):
                        text += "\n‼️ Внимание это тех.встреча!!"

                    overlap = is_overlap_with_support_planning(local_start, local_end)
                    if overlap:
                        text += "\n‼️ Внимание встреча пересекается с планеркой отдела тех.поддержки, перенесите встречу!!!"
                        markup = None
                    else:
                        take_btn = InlineKeyboardButton(
                            text="Взять встречу",
                            callback_data=f"take:{e['event_id']}"
                        )
                        markup = InlineKeyboardMarkup(inline_keyboard=[[take_btn]])

                    try:
                        if markup:
                            await bot.send_message(chat_id=BotConfig.SALES_CHAT_ID, text=text, reply_markup=markup)
                        else:
                            await bot.send_message(chat_id=BotConfig.SALES_CHAT_ID, text=text)
                    except Exception:
                        logger.exception("Failed to send day-in-day event.")
            else:
                old_start = existing.start_time
                old_end = existing.end_time
                new_start = e["start"]
                new_end = e["end"]

                start_changed = times_differ_enough(old_start, new_start)
                end_changed   = times_differ_enough(old_end, new_end)

                if start_changed or end_changed:
                    existing.start_time = new_start
                    existing.end_time = new_end
                    existing.title = e["title"]
                    db_sess.commit()

                    local_start = pytz.UTC.localize(new_start).astimezone(MOSCOW_TZ)
                    local_end = pytz.UTC.localize(new_end).astimezone(MOSCOW_TZ)

                    text = (
                        f"Встреча перенесена:\n{e['title']}\n"
                        f"Новое время: {local_start.strftime('%H:%M')} - {local_end.strftime('%H:%M')}"
                    )
                    if existing.is_technical:
                        text += "\n(Тех.встреча)"
                    overlap = is_overlap_with_support_planning(local_start, local_end)
                    if overlap:
                        text += "\n‼️ Внимание встреча пересекается с планеркой отдела тех.поддержки, перенесите встречу!!!"

                    try:
                        await bot.send_message(chat_id=BotConfig.SALES_CHAT_ID, text=text)
                    except Exception:
                        logger.exception("Failed to send 'moved' event.")

        # Проверяем, чего нет среди current_ids => "отменено"
        all_db_events = db_sess.query(Event).all()
        for db_ev in all_db_events:
            local_start = pytz.UTC.localize(db_ev.start_time).astimezone(MOSCOW_TZ)
            if local_start.date() == now_msk.date():
                if db_ev.event_id not in current_ids:
                    local_end = pytz.UTC.localize(db_ev.end_time).astimezone(MOSCOW_TZ)
                    if local_end > now_msk:
                        canceled_text = f"Встреча отменена:\n{db_ev.title}"
                        try:
                            await bot.send_message(chat_id=BotConfig.SALES_CHAT_ID, text=canceled_text)
                        except Exception:
                            logger.exception("Failed to send canceled event.")
                    db_sess.delete(db_ev)
                    db_sess.commit()
    finally:
        db_sess.close()

async def monthly_stats(bot: Bot):
    logger.debug("monthly_stats() called.")
    now_msk = datetime.now(MOSCOW_TZ)
    start_of_month = datetime(now_msk.year, now_msk.month, 1, 0, 0, 0, tzinfo=MOSCOW_TZ)
    end_of_month = datetime(now_msk.year, now_msk.month, now_msk.day, 23, 59, 59, tzinfo=MOSCOW_TZ)

    db_sess = Database.get_session()
    try:
        start_of_month_utc = start_of_month.astimezone(pytz.UTC).replace(tzinfo=None)
        end_of_month_utc = end_of_month.astimezone(pytz.UTC).replace(tzinfo=None)

        events_month = db_sess.query(Event).filter(
            Event.start_time >= start_of_month_utc,
            Event.end_time <= end_of_month_utc
        ).all()

        total_taken = 0
        per_user_stats = {}

        for ev in events_month:
            if ev.is_taken and ev.taken_by:
                total_taken += 1
                user = ev.taken_by
                if user not in per_user_stats:
                    per_user_stats[user] = {'count': 0, 'tech_count': 0}
                per_user_stats[user]['count'] += 1
                if ev.is_technical:
                    per_user_stats[user]['tech_count'] += 1

        msg_lines = [
            "Итоги месяца:",
            f"Всего взятых встреч: {total_taken}"
        ]
        if per_user_stats:
            msg_lines.append("\nПо сотрудникам:")
            for user, st in per_user_stats.items():
                msg_lines.append(
                    f"{user} — {st['count']} встреч(и), "
                    f"из них тех.встреч: {st['tech_count']}"
                )
        else:
            msg_lines.append("\n(Нет взятых встреч за этот период)")
        msg_text = "\n".join(msg_lines)

        try:
            await bot.send_message(chat_id=BotConfig.SUPPORT_CHAT_ID, text=msg_text)
        except Exception:
            logger.exception("Failed to send monthly stats.")
    finally:
        db_sess.close()

async def clean_old_data():
    logger.debug("clean_old_data() called.")
    now_msk = datetime.now(MOSCOW_TZ)
    cutoff = now_msk - timedelta(days=60)
    db_sess = Database.get_session()
    try:
        cutoff_utc = cutoff.astimezone(pytz.UTC).replace(tzinfo=None)
        old_events = db_sess.query(Event).filter(Event.end_time < cutoff_utc).all()
        for ev in old_events:
            logger.debug("Deleting old event %s / %s", ev.event_id, ev.title)
            db_sess.delete(ev)
        db_sess.commit()
    finally:
        db_sess.close()

async def main():
    logger.info("Starting main() ... Decrypting bot token.")
    decrypted_token = EncryptionManager.decrypt_value(
        BotConfig.ENCRYPTION_KEY,
        BotConfig.BOT_TOKEN_ENCRYPTED
    )
    logger.debug("Decrypted token ok, creating Bot...")

    bot = Bot(token=decrypted_token, parse_mode="HTML")
    dp = Dispatcher()

    dp.include_router(commands_router)
    dp.include_router(callbacks_router)

    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

    # Утреннее оповещение
    scheduler.add_job(
        morning_today_events, "cron",
        hour=7, minute=0,
        args=[bot]
    )
    # Проверка каждые 30 минут
    scheduler.add_job(
        check_for_updates, "interval",
        minutes=30,
        args=[bot]
    )
    # Ежемесячная статистика (последний день месяца, 20:00)
    scheduler.add_job(
        monthly_stats, "cron",
        day="last", hour=BotConfig.DAILY_NOTIFICATION_HOUR, minute=0,
        args=[bot]
    )
    # Очистка старых записей (последний день месяца, 20:10)
    scheduler.add_job(
        clean_old_data, "cron",
        day="last", hour=BotConfig.DAILY_NOTIFICATION_HOUR, minute=10
    )

    scheduler.start()

    await on_startup()
    logger.info("Dispatcher start_polling() now ...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
