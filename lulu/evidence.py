"""Bounded current-task evidence and checkable completion requirements."""
import re

NEGATED = re.compile(r'(?:不要|不得|禁止|别|无需|不用)[^，。；\n]*')
FILENAME = r'[^，。；\s“”"<>：:]+\.(?:docx|pdf|md|txt|xlsx|csv)'


def requirements(text):
    positive = NEGATED.sub('', text)
    names = re.findall(r'(?:保存为|命名为|文件名为)\s*[“"]?(' + FILENAME + ')', positive, re.I)
    for group in re.findall(r'(?:转换为|转成|转换成|另存为)\s*([^。；\n]+)',positive):
        for part in re.split(r'和|、|以及|及',group):
            match=re.match(r'\s*[“\"]?('+FILENAME+')',part)
            if match: names.append(match[1])
    return {
        'files': list(dict.fromkeys(names)),
        'file': bool(re.search(r'生成|新建|创建|保存|导出|写成|转成|转换', positive) and
                     (names or re.search(r'word|pdf|文档|文件', positive, re.I))),
        'memory': bool(re.search(r'记住|保存为长期记忆', positive)) and not bool(re.search(r'记住的|(?:记住|记得).{0,30}(?:什么|哪些|[？?])',positive)),
        'reminder': bool(re.search(r'(?:提醒我|设置.{0,6}提醒|添加.{0,6}提醒)', positive)),
        'no_memory': bool(re.search(r'(?:不要|不得|禁止|别)[^，。；\n]*(?:记忆|记住)', text)),
    }


def operation(name, args):
    if name in ('generate_document', 'create_document', 'convert_document', 'create_table'):
        return ('artifact', args.get('destination', args.get('path', '')))
    return (name, args.get('path', args.get('key', args.get('reminder_id', ''))))


def normalize_facts(text):
    text=re.sub(r'(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?',lambda m:f'{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}',text)
    return re.sub(r'\s+', '', text)


def factual_gaps(content, sources, request):
    """Check explicit labeled facts on source-based reports, not arbitrary prose quality."""
    if not sources or not re.search(r'总结|摘要|保留|整理|报告|提取', request):
        return []
    text = '\n'.join(sources)
    facts = re.findall(r'(?:代号|负责人|预算|截止日期|截止时间|参与人数|人数)\s*[：:]\s*([^，。；\n]+)', text)
    return [fact.strip() for fact in facts if fact.strip() and normalize_facts(fact) not in normalize_facts(content)]
