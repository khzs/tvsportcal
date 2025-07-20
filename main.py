from icalendar import Calendar, Event
from datetime import datetime, timedelta, time
from pydantic_settings import BaseSettings
import requests


class Settings(BaseSettings):
    filename: str = "calendar.ics"
    start_time_limit: time = time(11, 0)
    end_time_limit: time = time(22, 0)
    search_terms: dict = {
        "Heti helyzet": lambda p: True,
        "Lakers": lambda p: True,
        "NBA": lambda p: True,
        # "WNBA": lambda p: True,
        "Kézilabda: U19-es női Eb": lambda p: "Magyarország" in p.get("episode_title", ""),
        "Vizes világbajnokság": lambda p: "Női vízilabda" in p.get("episode_title", "") and "Magyarország" in p.get("episode_title", ""),
    }

settings = Settings()


def get_existing_event_keys(calendar):
    existing_event_keys = set()
    for component in calendar.walk():
        if component.name == "VEVENT":
            summary = str(component.get("SUMMARY"))
            dtstart = component.get("DTSTART").dt
            if isinstance(dtstart, datetime):
                dtstart = dtstart.replace(tzinfo=None).isoformat()
            existing_event_keys.add((summary, dtstart))
    return existing_event_keys


def build_url():
    url_base = "https://port.hu/tvapi"
    date_today = datetime.now().strftime("%Y-%m-%d")
    x_days_later = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")
    return f"{url_base}?channel_id[]=tvchannel-290&channel_id[]=tvchannel-90&channel_id[]=tvchannel-44&i_datetime_from={date_today}&i_datetime_to={x_days_later}"


if __name__ == '__main__':
    with open(settings.filename, "r") as f:
        calendar = Calendar.from_ical(f.read())

    url = build_url()
    data = requests.get(url).json()

    existing_event_keys = get_existing_event_keys(calendar)

    # Process all days and channels
    for day_data in data.values():
        for channel in day_data.get("channels", []):
            for program in channel.get("programs", []):
                title = program.get("title", "")
                episode_title = program.get("episode_title", "")
                start_dt_str = program.get("start_datetime", "")
                end_dt_str = program.get("end_datetime", "")

                try:
                    start_dt = datetime.fromisoformat(start_dt_str)
                    end_dt = datetime.fromisoformat(end_dt_str)
                except ValueError:
                    continue

                # Apply time filter
                if not (settings.start_time_limit <= start_dt.time() <= settings.end_time_limit):
                    continue

                # Match title to search term + run the corresponding rule
                for term, condition in settings.search_terms.items():
                    if term.lower() in title.lower() and condition(program):
                        summary = f"{title}, {episode_title}" if episode_title else title
                        key = (summary, start_dt.replace(tzinfo=None).isoformat())
                        if key not in existing_event_keys:
                            print(key)
                            event = Event()
                            event.add("SUMMARY", summary)
                            event.add("DTSTART", start_dt)
                            event.add("DTEND", end_dt)
                            calendar.add_component(event)
                            existing_event_keys.add(key)
                        break

    with open(settings.filename, "wb") as f:
        f.write(calendar.to_ical())
