import datetime
import logging
import pytz

from caldav import DAVClient, Calendar
from bot.config import BotConfig
from bot.encryption import EncryptionManager

logger = logging.getLogger(__name__)

def unify_dt_to_utc(dt: datetime.datetime) -> datetime.datetime:
    """
    Приводит dt к UTC, обрезает секунды/микросекунды (до минут),
    и убирает tzinfo (делает "naive", но фактически это UTC).
    """
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    else:
        dt = dt.astimezone(pytz.UTC)

    dt = dt.replace(second=0, microsecond=0)
    return dt.replace(tzinfo=None)

class CalDavClient:
    def __init__(self):
        logger.debug("CalDavClient __init__ start...")

        decrypted_password = EncryptionManager.decrypt_value(
            BotConfig.ENCRYPTION_KEY,
            BotConfig.CALDAV_ENCRYPTED_PASSWORD
        )
        logger.debug("Creating DAVClient with username=%s", BotConfig.CALDAV_USERNAME)

        direct_url = (
            "https://calendar.mail.ru/principals/multifactor.ru/support/"
            "calendars/f5b8cfdb-417c-4849-8116-2f7af84220e6"
        )
        self.client = DAVClient(
            url=direct_url,
            username=BotConfig.CALDAV_USERNAME,
            password=decrypted_password
        )
        self.calendar = None
        logger.debug("CalDavClient __init__ done.")

    def connect_calendar(self):
        logger.debug("connect_calendar called...")
        if self.calendar:
            logger.debug("Calendar already connected, skip.")
            return

        direct_calendar_url = (
            "https://calendar.mail.ru/principals/multifactor.ru/support/"
            "calendars/f5b8cfdb-417c-4849-8116-2f7af84220e6"
        )
        logger.debug("Using direct_calendar_url=%s", direct_calendar_url)

        self.calendar = Calendar(client=self.client, url=direct_calendar_url)
        logger.info("Calendar object created with direct URL: %s", direct_calendar_url)

    def get_upcoming_events(self, start_dt: datetime.datetime, end_dt: datetime.datetime):
        """
        Возвращает список событий (dict) из календаря за [start_dt, end_dt].
        start_dt/end_dt - в локальном времени, здесь приводим их
        к "naive UTC" через unify_dt_to_utc.
        """
        logger.debug("get_upcoming_events called for range [%s - %s]", start_dt, end_dt)

        start_dt_utc = unify_dt_to_utc(start_dt)
        end_dt_utc = unify_dt_to_utc(end_dt)

        if not self.calendar:
            self.connect_calendar()

        logger.debug(
            "Performing date_search on self.calendar with range [%s - %s]",
            start_dt_utc.isoformat(), end_dt_utc.isoformat()
        )
        results = self.calendar.date_search(start_dt_utc, end_dt_utc)
        logger.debug("date_search returned %d raw events", len(results))

        events = []
        for i, event_obj in enumerate(results, start=1):
            event_data = event_obj.instance.vevent

            title = event_data.summary.value
            uid = event_data.uid.value
            dt_start = event_data.dtstart.value
            dt_end = event_data.dtend.value

            dt_start_utc = unify_dt_to_utc(dt_start)
            dt_end_utc = unify_dt_to_utc(dt_end)

            logger.debug(
                "Event #%d: uid=%s, title=%s, start=%s, end=%s",
                i, uid, title, dt_start_utc.isoformat(), dt_end_utc.isoformat()
            )

            events.append({
                "event_id": uid,
                "title": title,
                "start": dt_start_utc,  # naive UTC
                "end": dt_end_utc      # naive UTC
            })

        logger.info(
            "Found %d events in calendar for the period [%s - %s].",
            len(events),
            start_dt_utc.isoformat(),
            end_dt_utc.isoformat()
        )
        return events
