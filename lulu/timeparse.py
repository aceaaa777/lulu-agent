"""Chinese natural-language time for reminders and alarms. Pure rules; the model never decides when something fires.

parse('明天早上8点提醒我开会') -> {'due': <epoch>, 'interval': 0, 'text': '开会', 'when': '明天 08:00'}
"""
import re
import time
from datetime import datetime, timedelta

CN_NUM = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '半': 30}
WEEKDAYS = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}


def cn_int(text):
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text == '十':
        return 10
    if '十' in text:
        left, _, right = text.partition('十')
        return (CN_NUM.get(left, 1) if left else 1)*10+(CN_NUM.get(right, 0) if right else 0)
    total = 0
    for ch in text:
        if ch not in CN_NUM:
            return None
        total = total*10+CN_NUM[ch]
    return total


NUM = r'(\d{1,4}|[零一二两三四五六七八九十]{1,3})'
CLOCK = re.compile(r'(?:(上午|早上|早晨|清晨|中午|下午|傍晚|晚上|夜里|凌晨)\s*)?'+NUM+r'\s*(?:点|时|:|：)\s*(?:(半)|'+NUM+r'\s*分?)?(?:\s*(上午|早上|下午|晚上))?')
RELATIVE = re.compile(r'(半|'+NUM[1:-1]+r')\s*(个)?\s*(秒|分钟|分|小时|钟头|天|日|周|星期)(?:之后|以后|后)')
DAY_WORDS = {'今天': 0, '今晚': 0, '明天': 1, '明早': 1, '明晚': 1, '后天': 2, '大后天': 3}
STRIP = re.compile(r'^(?:请|帮我|麻烦|给我)?(?:设(?:置|定)?(?:一个|个)?(?:闹钟|提醒)[，,：:]?|提醒我|叫我|喊我|记得|别忘了)\s*|\s*(?:提醒我|叫我|喊我)\s*$')


def _hour(period, hour):
    if period in ('下午', '傍晚', '晚上', '夜里') and hour < 12:
        hour += 12
    if period == '中午' and hour < 11:
        hour += 12
    if period in ('凌晨',) and hour == 12:
        hour = 0
    return hour


def _next_weekday(base, weekday, next_week=False):
    """周X = that day this week if still ahead (today counts), else next week; 下周X = that day of the next calendar week."""
    if next_week:
        monday_next = base+timedelta(days=7-base.weekday())
        return monday_next+timedelta(days=weekday)
    return base+timedelta(days=(weekday-base.weekday()) % 7)


def parse(text, now=None):
    """Return {'due','interval','text','when'} or None when no time expression is found."""
    now = now or datetime.now()
    original = text.strip()
    body = original
    interval = 0
    due = None
    when = ''

    # recurring: 每天/每周X/每小时/每隔N分钟
    every = re.search(r'每\s*(?:隔\s*)?'+NUM+r'?\s*(天|日|小时|个小时|分钟|周|星期)', body)
    weekday_every = re.search(r'每\s*(?:周|星期)([一二三四五六日天])', body)
    weekly_base = None
    if weekday_every:
        interval = 7*86400
        weekly_base = _next_weekday(now, WEEKDAYS[weekday_every.group(1)])
    elif every:
        n = cn_int(every.group(1)) or 1
        unit = every.group(2)
        interval = n*({'天': 86400, '日': 86400, '小时': 3600, '个小时': 3600, '分钟': 60, '周': 604800, '星期': 604800}[unit])
    if every or weekday_every:
        body = re.sub(r'每\s*(?:隔\s*)?'+NUM+r'?\s*(?:天|日|小时|个小时|分钟|周|星期)([一二三四五六日天])?', ' ', body)

    # relative: N分钟后
    rel = RELATIVE.search(body)
    if rel:
        unit = rel.group(3)
        seconds_per = {'秒': 1, '分钟': 60, '分': 60, '小时': 3600, '钟头': 3600, '天': 86400, '日': 86400, '周': 604800, '星期': 604800}[unit]
        if rel.group(1) == '半':
            seconds = seconds_per//2
            when = '半'+unit+'后'
        else:
            n = cn_int(rel.group(1))
            seconds = n*seconds_per
            when = f'{n}{unit}后'
        due = now+timedelta(seconds=seconds)
        body = body[:rel.start()]+' '+body[rel.end():]
    else:
        day_offset = 0 if weekly_base else None
        base = weekly_base or now
        for word, offset in DAY_WORDS.items():
            if word in body:
                day_offset = offset
                body = body.replace(word, ' ')
                if word.endswith('晚'):
                    body = '晚上 '+body
                if word == '明早':
                    body = '早上 '+body
                break
        wd = re.search(r'(下+)?\s*(?:周|星期|礼拜)([一二三四五六日天])', body)
        if wd:
            target = _next_weekday(now, WEEKDAYS[wd.group(2)], bool(wd.group(1)))
            base = target
            day_offset = 0
            body = body[:wd.start()]+' '+body[wd.end():]
        date = re.search(NUM+r'\s*月\s*'+NUM+r'\s*[日号]', body)
        if date:
            month, day = cn_int(date.group(1)), cn_int(date.group(2))
            try:
                base = now.replace(month=month, day=day)
                if base.date() < now.date():
                    base = base.replace(year=now.year+1)
            except ValueError:
                return None
            day_offset = 0
            body = body[:date.start()]+' '+body[date.end():]
        clock = CLOCK.search(body)
        bare_period = re.search(r'(早上|早晨|清晨|上午|中午|下午|傍晚|晚上|夜里|凌晨)', body) if not clock else None
        if not clock and bare_period and (day_offset is not None or wd or date or interval):
            hour = {'早上': 8, '早晨': 8, '清晨': 7, '上午': 9, '中午': 12, '下午': 15, '傍晚': 18, '晚上': 20, '夜里': 22, '凌晨': 6}[bare_period.group(1)]
            due = (base+timedelta(days=day_offset or 0)).replace(hour=hour, minute=0, second=0, microsecond=0)
            body = body[:bare_period.start()]+' '+body[bare_period.end():]
            when = '（按'+bare_period.group(1)+'默认时间）'
        elif clock:
            period = clock.group(1) or clock.group(5) or ''
            hour = cn_int(clock.group(2))
            minute = 30 if clock.group(3) else (cn_int(clock.group(4)) or 0)
            if hour is None or hour > 24 or minute > 59:
                return None
            hour = _hour(period, hour) % 24
            base = base if day_offset is not None else now
            due = base.replace(hour=hour, minute=minute, second=0, microsecond=0)+timedelta(days=day_offset or 0)
            if day_offset is None and due <= now:
                due += timedelta(days=1)
            body = body[:clock.start()]+' '+body[clock.end():]
        elif day_offset is not None or wd or date:
            due = (base+timedelta(days=day_offset or 0)).replace(hour=9, minute=0, second=0, microsecond=0)
            if wd and due <= now:
                due += timedelta(days=7)
            when = '（未说时间，默认早上九点）'
        elif interval:
            due = now+timedelta(seconds=interval)
    if due is None:
        return None
    if due <= now and interval:
        while due <= now:
            due += timedelta(seconds=interval)
    if due <= now:
        return {'error': '这个时间已经过了（'+due.strftime('%m月%d日 %H:%M')+'），请说一个之后的时间。'}
    if not rel:
        when = due.strftime('%m月%d日 %H:%M')+(when if when.startswith('（') else '')
    body = re.sub(r'(?:早上|早晨|清晨|上午|中午|下午|傍晚|晚上|夜里|凌晨)\s', ' ', body)
    body = re.sub(r'(?:请|帮我|麻烦|给我)?(?:设(?:置|定)?(?:一个|个)?(?:闹钟|提醒)|定个闹钟)[，,：:]?', ' ', body)
    body = STRIP.sub('', re.sub(r'\s+', ' ', body)).strip(' ，,。！!、：:')
    body = re.sub(r'^(?:提醒我|叫我|记得|喊我)', '', body).strip(' ，,。')
    body = re.sub(r'(?:提醒我|叫我|喊我)$', '', body).strip(' ，,。')
    label = when
    if interval:
        label += '，每'+({86400: '天', 3600: '小时', 604800: '周'}.get(interval, f'{interval//60}分钟'))+'重复'
    return {'due': due.timestamp(), 'interval': interval, 'text': body or '到时间了', 'when': label}


def looks_like_reminder(text):
    return bool(re.search(r'提醒|闹钟|叫我|喊我|别忘了|记得.{0,12}(?:点|分钟|小时|明天|今天|周)', text))
