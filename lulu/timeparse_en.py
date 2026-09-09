"""English natural-language time for reminders and alarms. Same contract as timeparse.parse (the Chinese one):

parse('remind me to call Sam tomorrow at 8am') -> {'due': <epoch>, 'interval': 0, 'text': 'call Sam', 'when': 'Tue 09/09 08:00'}

Rules first because a reminder that fires at the wrong time is a silent failure; when nothing here matches, the remind
skill asks the model (see skills.model_parse_time) and echoes the parsed time back in its reply.
"""
import re
from datetime import datetime, timedelta

WORD_NUM = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'eleven': 11, 'twelve': 12, 'fifteen': 15, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'other': 2}
UNIT_SECONDS = {'second': 1, 'sec': 1, 'minute': 60, 'min': 60, 'hour': 3600, 'hr': 3600, 'day': 86400, 'week': 604800, 'wk': 604800}
WEEKDAYS = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
PERIOD_HOUR = {'morning': 8, 'noon': 12, 'midday': 12, 'afternoon': 15, 'evening': 19, 'tonight': 20, 'night': 21, 'midnight': 0}
NUM = r'(\d{1,4}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|sixty|half an|half a)'
UNIT = r'(second|sec|minute|min|hour|hr|day|week|wk)s?'
RELATIVE = re.compile(r'\b(?:in|after|within)\s+'+NUM+r'\s+'+UNIT+r'\b|\b'+NUM+r'\s+'+UNIT+r'\s+(?:from now|later)\b', re.I)
EVERY = re.compile(r'\b(?:every|each)\s+(?:'+NUM+r'\s+)?'+UNIT+r'\b|\b(daily|weekly|hourly)\b(?!\s+(?:report|meeting|review|update|summary|newsletter|call|sync|digest|plan|log|check-?in))', re.I)
EVERY_WEEKDAY = re.compile(r'\b(?:every|each)\s+(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b', re.I)
EVERY_PERIOD = re.compile(r'\b(?:every|each)\s+(morning|afternoon|evening|night)\b', re.I)
UNIT_NC = r'(?:second|sec|minute|min|hour|hr|day|week|wk)s?'
CLOCK = re.compile(r'\b(?:at\s+)?(?P<h1>\d{1,2})(?::(?P<m1>\d{2}))?\s*(?P<ampm>a\.?m\.?|p\.?m\.?)(?![a-z])'
                   r'|\bat\s+(?P<h2>\d{1,2})(?::(?P<m2>\d{2}))?\b(?!\s*(?:'+UNIT_NC+r'|am|pm|st|nd|rd|th|/|-|:))'
                   r'|\b(?P<h3>\d{1,2}):(?P<m3>\d{2})\b(?!\s*(?:'+UNIT_NC+r'|am|pm|/|-|:))'
                   r'|\b(?P<word>noon|midday|midnight)\b', re.I)
WEEKDAY = re.compile(r'\b(next|this|on|coming)?\s*(mon|tue|wed|thu|fri|sat|sun)(?:day|sday|nesday|rsday|urday)?\b', re.I)
DAY_WORDS = re.compile(r'\b(?:(?:the\s+)?day after tomorrow|tomorrow|tmrw|tmr|tonight|today)\b', re.I)
DAY_OFFSET = {'day after tomorrow': 2, 'the day after tomorrow': 2, 'tomorrow': 1, 'tmrw': 1, 'tmr': 1, 'tonight': 0, 'today': 0}
DATE_ISO = re.compile(r'\b(20\d{2})-(\d{1,2})-(\d{1,2})\b')
DATE_US = re.compile(r'\b(\d{1,2})/(\d{1,2})(?:/(20\d{2}|\d{2}))?\b')
DATE_MONTH = re.compile(r'\b(?:on\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s*(20\d{2}))?|\b(?:on\s+)?(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b', re.I)
PERIOD = re.compile(r'\b(?:in\s+the\s+|this\s+|at\s+)?(morning|afternoon|evening|night|noon|midday|midnight)\b', re.I)
CUES = re.compile(r'^\s*(?:hey\s+lulu[,!]?\s*)?(?:please|pls|could you|can you|would you)?\s*(?:remind me\s*(?:to|about|of|that)?|set\s+(?:a|an|up a)?\s*(?:reminder|alarm|timer)\s*(?:for|to|about|:)?|(?:a\s+)?reminder\s*(?:for|to|about|:)?|alarm\s*(?:for|at)?|don\'?t\s+(?:let me\s+)?forget\s*(?:to|about)?|remember\s+to|wake me\s*(?:up)?|ping me\s*(?:to|about)?|alert me\s*(?:to|about)?)\s*', re.I)
TAIL = re.compile(r'\s*(?:,?\s*please|,?\s*thanks|,?\s*thank you|remind me|,?\s*ok\??)\s*$', re.I)


def _num(word):
    if not word:
        return 1
    w = word.lower().strip()
    if w.isdigit():
        return int(w)
    if w.startswith('half'):
        return 0.5
    return WORD_NUM.get(w, 1)


def _cut(text, match):
    return text[:match.start()]+' '+text[match.end():]


def _next_weekday(base, weekday, next_week=False):
    """'friday' = that day this week if still ahead (today counts), else next week; 'next friday' = that day of the next calendar week."""
    if next_week:
        monday_next = base+timedelta(days=7-base.weekday())
        return monday_next+timedelta(days=weekday)
    return base+timedelta(days=(weekday-base.weekday()) % 7)


def _label(due):
    return due.strftime('on %a %m/%d at %H:%M')


def parse(text, now=None):
    """Return {'due','interval','text','when'}, {'error': …} for a time already past, or None when no time is found."""
    now = now or datetime.now()
    body = ' '+text.strip()+' '
    interval = 0
    due = None
    when = ''
    weekly_base = None
    default_hour = None

    # recurring
    m = EVERY_WEEKDAY.search(body)
    if m:
        interval = 604800
        weekly_base = _next_weekday(now, WEEKDAYS[m.group(1).lower()[:3]])
        body = _cut(body, m)
    else:
        m = EVERY_PERIOD.search(body)
        if m:
            interval = 86400
            default_hour = PERIOD_HOUR[m.group(1).lower()]
            body = _cut(body, m)
        else:
            m = EVERY.search(body)
            if m:
                if m.group(3):
                    interval = {'daily': 86400, 'weekly': 604800, 'hourly': 3600}[m.group(3).lower()]
                else:
                    n = _num(m.group(1))
                    interval = int(n*UNIT_SECONDS[m.group(2).lower().rstrip('s') if m.group(2).lower() not in UNIT_SECONDS else m.group(2).lower()])
                body = _cut(body, m)

    # relative: in 10 minutes / 2 hours from now
    rel = RELATIVE.search(body)
    if rel:
        n = _num(rel.group(1) or rel.group(3))
        unit = (rel.group(2) or rel.group(4)).lower()
        unit = unit if unit in UNIT_SECONDS else unit.rstrip('s')
        seconds = n*UNIT_SECONDS[unit]
        due = now+timedelta(seconds=seconds)
        pretty = {'sec': 'second', 'min': 'minute', 'hr': 'hour', 'wk': 'week'}.get(unit, unit)
        count = int(n) if float(n).is_integer() else n
        when = f'in {count} {pretty}'+('' if count == 1 else 's') if count != 0.5 else f'in half an {pretty}' if pretty == 'hour' else f'in half a {pretty}'
        body = _cut(body, rel)
    else:
        day_offset = 0 if weekly_base else None
        base = weekly_base or now
        dw = DAY_WORDS.search(body)
        if dw:
            word = re.sub(r'\s+', ' ', dw.group(0).lower())
            day_offset = DAY_OFFSET[word]
            if word == 'tonight':
                default_hour = default_hour or PERIOD_HOUR['tonight']
            body = _cut(body, dw)
        wd = WEEKDAY.search(body)
        if wd and not weekly_base:
            base = _next_weekday(now, WEEKDAYS[wd.group(2).lower()[:3]], (wd.group(1) or '').lower() == 'next')
            day_offset = 0
            body = _cut(body, wd)
        elif wd:
            body = _cut(body, wd)
        date = DATE_ISO.search(body) or DATE_MONTH.search(body) or DATE_US.search(body)
        if date:
            g = date.groups()
            try:
                if date.re is DATE_ISO:
                    base = now.replace(year=int(g[0]), month=int(g[1]), day=int(g[2]))
                elif date.re is DATE_MONTH:
                    month = MONTHS[(g[0] or g[4]).lower()[:3]]
                    day = int(g[1] or g[3])
                    base = now.replace(month=month, day=day, year=int(g[2]) if g[2] else now.year)
                else:
                    year = int(g[2]) if g[2] else now.year
                    year = year+2000 if year < 100 else year
                    base = now.replace(year=year, month=int(g[0]), day=int(g[1]))
                if base.date() < now.date() and not (date.re is DATE_ISO or (date.re is DATE_US and g[2]) or (date.re is DATE_MONTH and g[2])):
                    base = base.replace(year=now.year+1)
            except ValueError:
                return None
            day_offset = 0
            body = _cut(body, date)
        clock = CLOCK.search(body)
        period = PERIOD.search(body) if not clock else None
        if clock:
            g = clock.groupdict()
            if g['word']:
                hour, minute = PERIOD_HOUR[g['word'].lower()], 0
            else:
                hour = int(g['h1'] or g['h2'] or g['h3'])
                minute = int(g['m1'] or g['m2'] or g['m3'] or 0)
                ampm = (g['ampm'] or '').lower().replace('.', '')
                if ampm == 'pm' and hour < 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
                elif not ampm and hour <= 7 and hour != 0 and not re.search(r'\bmorning\b', body, re.I):
                    hour += 12   # "at 3" means the afternoon unless the morning is mentioned
            if hour > 24 or minute > 59:
                return None
            hour %= 24
            base = base if day_offset is not None else now
            due = base.replace(hour=hour, minute=minute, second=0, microsecond=0)+timedelta(days=day_offset or 0)
            if day_offset is None and due <= now:
                due += timedelta(days=1)
            body = _cut(body, clock)
            trailing = PERIOD.search(body)
            if trailing and trailing.group(1).lower() in ('morning', 'afternoon', 'evening', 'night'):
                body = _cut(body, trailing)
        elif period and (day_offset is not None or wd or date or interval or default_hour is not None):
            hour = PERIOD_HOUR[period.group(1).lower()]
            due = (base+timedelta(days=day_offset or 0)).replace(hour=hour, minute=0, second=0, microsecond=0)
            body = _cut(body, period)
            when = f'(using the usual {period.group(1).lower()} time)'
        elif day_offset is not None or wd or date or default_hour is not None:
            hour = default_hour if default_hour is not None else 9
            due = (base+timedelta(days=day_offset or 0)).replace(hour=hour, minute=0, second=0, microsecond=0)
            if wd and due <= now:
                due += timedelta(days=7)
            if default_hour is None:
                when = '(No time given; using 9 AM)'
        elif interval:
            due = now+timedelta(seconds=interval)
    if due is None:
        return None
    if due <= now and interval:
        while due <= now:
            due += timedelta(seconds=interval)
    if due <= now:
        return {'error': 'That time has already passed ('+due.strftime('%a %m/%d %H:%M')+'). Please choose a later time.'}
    if not rel:
        when = _label(due)+(' '+when if when.startswith('(') else '')
    body = re.sub(r'\s+', ' ', body).strip(' ,.!:;-')
    body = CUES.sub('', body)
    body = TAIL.sub('', body)
    body = re.sub(r'^(?:to|about|that|for|at|on)\s+', '', body, flags=re.I)
    body = re.sub(r'\s+(?:at|on|for|by)$', '', body, flags=re.I).strip(' ,.!:;-')
    label = when
    if interval:
        label += ', every '+({86400: 'day', 3600: 'hour', 604800: 'week'}.get(interval, f'{interval//3600} hours' if interval % 3600 == 0 else f'{interval//60} minutes'))
    return {'due': due.timestamp(), 'interval': interval, 'text': body or "It's time", 'when': label}


def looks_like_reminder(text):
    return bool(re.search(r"\b(?:remind|reminder|alarm|timer|don'?t forget|wake me|ping me|alert me)\b", text, re.I))
