"""Resolve explicit conversation exports without asking a model to invent a file."""
import json
import re


COMMAND=re.compile(r'(?:请)?(?:帮我)?(?:把|将)?\s*(?:上面(?:的|那段|这段)?(?:话|内容|文字|回答)?|这段(?:话|内容|文字)|刚才(?:的)?(?:话|内容|回答)|以上(?:内容|文字)?|这些话)\s*(?:写成|生成|导出(?:成|为)?|保存(?:成|为)?|转(?:换)?(?:成|为))\s*(?:一[份个]\s*)?(pdf|word|docx)(?:\s*(?:文件|文档))?[。！!\s]*$',re.I)


def split_export(text):
    match=COMMAND.search(text.strip())
    if not match:
        return None
    raw_prefix=text.strip()[:match.start()]
    prefix=raw_prefix.strip()
    # Only separate a trailing instruction from its supplied body. Quoted examples
    # and negated instructions must not trigger automatic document creation.
    if prefix and not (prefix.endswith(('。','！','!')) or '\n' in raw_prefix):
        return None
    if prefix.endswith(('不要','别','不能')): return None
    return prefix, 'docx' if match.group(1).lower() in ('word','docx') else 'pdf'


def resolve_export(store,tid,text):
    parsed=split_export(text)
    if parsed is None: return None
    body,extension=parsed
    if body: return {'text':body,'extension':extension,'source_task':tid}
    current=store.task(tid)
    previous=store.rows('SELECT * FROM tasks WHERE session=? AND epoch=? AND created<? ORDER BY created DESC LIMIT 30',
                        (current['session'],store.epoch,current['created']))
    for task in previous:
        exports=store.rows("SELECT detail FROM events WHERE task=? AND epoch=? AND kind='conversation_export' ORDER BY id DESC LIMIT 1",
                           (task['id'],store.epoch))
        if exports:
            source=json.loads(exports[0]['detail'])
            return {'text':source['text'],'extension':extension,'source_task':source['source_task']}
        earlier=split_export(task['goal'])
        if earlier:
            if earlier[0]: return {'text':earlier[0],'extension':extension,'source_task':task['id']}
            continue
        if task['status']=='completed' and task['answer']:
            return {'text':task['answer'],'extension':extension,'source_task':task['id']}
    raise ValueError('没有找到要导出的正文。请把文字粘贴过来，或先让我写好内容，再说“把上面的内容导出为PDF”。')
