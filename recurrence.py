import datetime
import re


def days_range(start_date, end_date):
    delta = end_date - start_date
    return [start_date + datetime.timedelta(days=i) for i in range(delta.days + 1)]

def delta_hours(delta):
    return (delta.total_seconds() / 60) / 60

def from_string(string):
    string = string.strip().lower()
    if string.startswith("daily"):
        if at := re.match("^daily(?: at (\d?\d:\d\d))?", string).group(1):
            return {"recurs": "daily", "at": datetime.time.fromisoformat(at.strip())}
        return {"recurs": "daily"}
    if match := re.match("^(weekly|monthly|annually)(?: on (\S+)(?: at (\d?\d:\d\d))?)?", string):
        res = {"recurs": match.group(1)}
        if on := match.group(2):
            res["on"] = on.strip()
            if at := match.group(3):
                res["at"] = datetime.time.fromisoformat(at.strip())
        return res

def validate(string):
    return bool(from_string(string))

def to_string(rec):
    on = f"on {rec['on']}" if rec['on'] else None
    at = f"at {rec['at']}" if rec['at'] else None
    r = rec['recurs']
    return " ".join(el for el in [r, on, at] if el is not None)

def should_recur_p(rec, last_checked, now=None):
    if now is None:
        now = datetime.datetime.now()
    delta = now - last_checked
    if rec['recurs'] == "daily":
        days = 1
    elif rec['recurs'] == "weekly":
        days = 7
    elif rec['recurs'] == "monthly":
        days = 30
    elif rec['recurs'] == "annually":
        days = 365

    hours = (days * 24) - int(days * 0.1)

    day_check = (delta.days >= days) or (delta_hours(delta) >= hours)

    if at := rec.get('at'):
        return day_check or (delta.days == days and now.hour >= rec['at'].hour)

    return day_check
