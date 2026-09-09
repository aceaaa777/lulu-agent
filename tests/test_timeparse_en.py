"""English reminder times (the English build routes timeparse.parse here; the Chinese parser is untouched)."""
import asyncio
import json
from datetime import datetime

import pytest

from lulu import timeparse, timeparse_en
from lulu.models import ModelProvider, Reply

NOW = datetime(2026, 9, 8, 15, 0)   # a Tuesday afternoon


def at(result):
    return datetime.fromtimestamp(result['due']).strftime('%a %m/%d %H:%M')


@pytest.mark.parametrize('text,when,task,interval', [
    ('remind me to call Sam tomorrow at 8am', 'Wed 09/09 08:00', 'call Sam', 0),
    ('In 30 minutes', 'Tue 09/08 15:30', "It's time", 0),
    ('remind me in half an hour to check the oven', 'Tue 09/08 15:30', 'check the oven', 0),
    ('set an alarm for 6:30 pm', 'Tue 09/08 18:30', "It's time", 0),
    ('remind me at 3 to pick up the kids', 'Wed 09/09 15:00', 'pick up the kids', 0),        # 3 pm has passed → tomorrow
    ('remind me at 9 tomorrow morning to call the bank', 'Wed 09/09 09:00', 'call the bank', 0),
    ('next monday morning dentist', 'Mon 09/14 08:00', 'dentist', 0),
    ('on friday submit the report', 'Fri 09/11 09:00', 'submit the report', 0),
    ('Sep 11 at 10:00 flight', 'Fri 09/11 10:00', 'flight', 0),
    ('call mom on the 15th of October', 'Thu 10/15 09:00', 'call mom', 0),
    ('2026-12-24 20:00 party', 'Thu 12/24 20:00', 'party', 0),
    ('tonight water the plants', 'Tue 09/08 20:00', 'water the plants', 0),
    ('meeting at 14:30', 'Wed 09/09 14:30', 'meeting', 0),
    ('please remind me to submit my weekly report tomorrow at 3 PM', 'Wed 09/09 15:00', 'submit my weekly report', 0),
    ('every friday at 9am standup', 'Fri 09/11 09:00', 'standup', 604800),
    ('every day at 22:00 take meds', 'Tue 09/08 22:00', 'take meds', 86400),
    ('remind me to stretch every 20 minutes', 'Tue 09/08 15:20', 'stretch', 1200),
    ('every 2 hours drink water', 'Tue 09/08 17:00', 'drink water', 7200),
    ('remind me every monday at 9am weekly report', 'Mon 09/14 09:00', 'weekly report', 604800),
])
def test_english_times(text, when, task, interval):
    result = timeparse_en.parse(text, NOW)
    assert result and 'due' in result, result
    assert at(result) == when
    assert result['text'] == task
    assert result['interval'] == interval


def test_no_time_and_past_time():
    assert timeparse_en.parse('hello there', NOW) is None
    assert timeparse_en.parse('pay rent on the 1st', NOW) is None          # left to the model
    past = timeparse_en.parse('remind me at 2pm today to email Bob', NOW)
    assert 'error' in past and 'already passed' in past['error']


def test_labels_read_naturally():
    assert timeparse_en.parse('in 10 minutes', NOW)['when'] == 'in 10 minutes'
    assert timeparse_en.parse('remind me tomorrow', NOW)['when'] == 'on Wed 09/09 at 09:00 (No time given; using 9 AM)'
    assert timeparse_en.parse('every 2 hours drink water', NOW)['when'].endswith(', every 2 hours')


def test_looks_like_reminder():
    assert timeparse_en.looks_like_reminder("Don't forget to call Ana")
    assert timeparse_en.looks_like_reminder('set an alarm for 6')
    assert not timeparse_en.looks_like_reminder('summarize this file')


def test_build_language_routes_the_parser(monkeypatch):
    monkeypatch.setattr(timeparse, 'LANG', 'en')
    assert at(timeparse.parse('tomorrow at 8am', NOW)) == 'Wed 09/09 08:00'
    assert timeparse.looks_like_reminder('remind me')
    monkeypatch.setattr(timeparse, 'LANG', 'zh')
    assert at(timeparse.parse('明天早上8点提醒我开会', NOW)) == 'Wed 09/09 08:00'
    assert timeparse.parse('tomorrow at 8am', NOW) is None


class Answers(ModelProvider):
    def __init__(self, payload):
        super().__init__('scripted', 'http://127.0.0.1:1')
        self.payload = payload
        self.prompts = []

    async def chat(self, messages, tools=None, *, schema=None, **kwargs):
        self.prompts.append((schema['title'] if schema else None, messages))
        return Reply(content=json.dumps(self.payload))


def test_model_fallback_does_the_arithmetic():
    from lulu import skills

    class Run:
        provider = Answers({'date': '2026-10-01', 'time': '09:00', 'repeat': 'none', 'task': 'pay rent'})

        class budget:
            @staticmethod
            def step_timeout(a, b):
                return 30
    result = asyncio.run(skills.model_parse_time(Run(), 'remind me to pay rent on the 1st', NOW))
    assert at(result) == 'Thu 10/01 09:00' and result['text'] == 'pay rent' and result['by_model']
    assert Run.provider.prompts[0][0] == 'when' and 'Tuesday, 2026-09-08 15:00' in Run.provider.prompts[0][1][0]['content']
    Run.provider = Answers({'date': '2026-09-08', 'time': '08:00', 'repeat': 'daily', 'task': 'stretch'})
    result = asyncio.run(skills.model_parse_time(Run(), 'stretch every morning at 8', NOW))
    assert at(result) == 'Wed 09/09 08:00' and result['interval'] == 86400      # today's 08:00 has passed → rolls forward
    Run.provider = Answers({'date': 'unknown', 'time': '', 'repeat': 'none', 'task': ''})
    assert asyncio.run(skills.model_parse_time(Run(), 'whenever', NOW)) is None
