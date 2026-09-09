"""桌宠动作由任务最新事件决定：动手阶段敲键盘（working），纯思考阶段做思考动作（thinking）。

回归背景：0.5 技能表之后只有旧工具循环发 tool_started，服务端却只认它，导致桌宠永远在"想"，敲键盘动画再没出现过。
"""
from lulu.server import animation_for, WORKING_KINDS


def test_skill_stages_type():
    for kind in ['skill_started', 'translate_started', 'rewrite_started', 'extract_started', 'drafting', 'tool_started',
                 'research_started', 'search_started', 'pages_fetched', 'translate_retry', 'generate_retry']:
        assert animation_for(kind) == 'working', kind


def test_chat_and_memory_skills_think_even_when_started():
    assert animation_for('skill_started', {'skill': 'chat'}) == 'thinking'
    assert animation_for('skill_started', {'skill': 'memory_qa'}) == 'thinking'
    assert animation_for('skill_started', {'skill': 'translate'}) == 'working'


def test_pure_thinking_stages_think():
    for kind in ['', 'thinking', 'intent', 'plan', 'memory_used', 'history_attached', 'draft_result', 'user_input_required']:
        assert animation_for(kind) == 'thinking', kind


def test_every_started_event_is_working():
    # 以后新增 xxx_started 事件时别忘了加进 WORKING_KINDS——用源码里的事件名核对
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'lulu'
    kinds = set()
    for f in root.glob('*.py'):
        kinds |= set(re.findall(r"event\((?:tid, ?)?'([a-z_]+_started)'", f.read_text(encoding='utf-8')))
    assert kinds, 'no *_started events found'
    assert kinds <= WORKING_KINDS, kinds - WORKING_KINDS
