"""Task intent: one schema-constrained classification call, checked and corrected by deterministic rules.

The model picks from enumerations (a job a small model does reliably); the program owns negations, filenames
and anything that can be verified against the workspace.
"""
import json
import re

from .evidence import requirements, NEGATED

TASK_TYPES = ['new_document', 'summarize_file', 'convert', 'edit', 'analyze_table', 'reminder', 'memory', 'question',
              'search', 'export_conversation', 'chat', 'other']
DOCUMENT_KINDS = ['report', 'plan', 'summary', 'letter', 'questionnaire', 'confirmation_letter', 'checklist', 'template', 'other', 'none']
DELIVERABLES = ['docx', 'pdf', 'md', 'txt', 'xlsx', 'csv', 'none']
REALTIME_TOPICS = ['crypto_price', 'stock', 'fx', 'weather', 'news', 'none']

SCHEMA = {
    'title': 'intent', 'type': 'object', 'additionalProperties': False,
    'properties': {
        'task_type': {'type': 'string', 'enum': TASK_TYPES},
        'deliverable': {'type': 'string', 'enum': DELIVERABLES},
        'document_kind': {'type': 'string', 'enum': DOCUMENT_KINDS},
        'needs_realtime': {'type': 'boolean'},
        'realtime_topic': {'type': 'string', 'enum': REALTIME_TOPICS},
        'symbols': {'type': 'array', 'items': {'type': 'string'}},
        'platforms': {'type': 'array', 'items': {'type': 'string'}},
        'input_files': {'type': 'array', 'items': {'type': 'string'}},
        'remember': {'type': 'boolean'},
        'explicit_template': {'type': 'boolean'},
        'confidence': {'type': 'number'},
    },
    'required': ['task_type', 'deliverable', 'document_kind', 'needs_realtime', 'realtime_topic', 'symbols', 'platforms',
                 'input_files', 'remember', 'explicit_template', 'confidence'],
}

SYSTEM = ('你是任务分类器。只输出JSON，不解释。根据用户的一句话判断：task_type（任务类型）、deliverable（要生成的文件格式，'
          '没有则none）、document_kind（文档种类；用户明确要问卷、确认函、清单、模板时选对应项）、needs_realtime（是否需要今天/实时/最新的外部数据，'
          '例如价格、行情、天气、新闻；只根据用户已有资料或常识就能写的选false）、realtime_topic、symbols（币种/股票代码，大写）、'
          'platforms（交易所或平台名，小写英文，例如binance、okx、coinbase）、input_files（用户提到的已有文件名，原样）、'
          'remember（用户要求长期记住某偏好）、explicit_template（用户明确要空模板/示例而不是真实数据）、confidence（0到1）。'
          '用户的否定要求（不要、别、禁止）不是任务目标。')

PLATFORM_ALIASES = {'币安': 'binance', 'binance': 'binance', '欧易': 'okx', 'okx': 'okx', 'okex': 'okx', 'coinbase': 'coinbase',
                    'kraken': 'kraken', 'bybit': 'bybit', 'gate': 'gate', 'huobi': 'htx', 'htx': 'htx', 'bitget': 'bitget', 'coingecko': 'coingecko'}
SYMBOL_WORDS = {'比特币': 'BTC', 'btc': 'BTC', '以太坊': 'ETH', '以太': 'ETH', 'eth': 'ETH', 'sol': 'SOL', 'bnb': 'BNB', 'doge': 'DOGE', 'xrp': 'XRP', 'usdt': 'USDT'}


def template_request(goal):
    positive = NEGATED.sub('', goal)
    return bool(re.search(r'模板|示例|问卷|确认函|问题清单|采访提纲|待办清单', positive))


def realtime_request(goal):
    positive = NEGATED.sub('', goal)
    return not template_request(goal) and bool(re.search(r'今日|今天|最新|实时|当前|现在', positive) and re.search(r'价格|行情|走势|汇率|新闻|天气|股价|币价|多少钱|报价', positive))


def heuristic(text, listing=()):
    """Rule-based intent. Used when the model cannot classify, and as the reference the model answer is checked against."""
    positive = NEGATED.sub('', text)
    contract = requirements(text)
    lower = positive.lower()
    deliverable = 'none'
    for ext in ('docx', 'pdf', 'xlsx', 'csv', 'md', 'txt'):
        if contract['files'] and contract['files'][0].lower().endswith('.'+ext):
            deliverable = ext; break
    if deliverable == 'none' and contract['file']:
        deliverable = 'docx' if re.search(r'word|docx', lower) else 'pdf' if 'pdf' in lower else 'xlsx' if re.search(r'excel|xlsx|表格', lower) else 'md'
    mentioned = [item['path'] for item in listing if item['path'] in text]
    if re.search(r'分钟后提醒|小时后提醒|提醒我', positive) and not contract['file']:
        task_type = 'reminder'
    elif contract['memory'] and not contract['file']:
        task_type = 'memory'
    elif re.search(r'(?:上面|这段|刚才|以上).{0,8}(?:写成|生成|导出|保存|转)', positive):
        task_type = 'export_conversation'
    elif re.search(r'(?:分析|统计|计算)', positive) and re.search(r'\.(?:csv|tsv|xlsx)', lower):
        task_type = 'analyze_table'
    elif re.search(r'改成|改为|替换', positive) and mentioned:
        task_type = 'edit'
    elif re.search(r'转换|转成|另存', positive) and mentioned and not re.search(r'总结|摘要|分析', positive):
        task_type = 'convert'
    elif re.search(r'总结|摘要|提取|概括', positive) and (mentioned or re.search(r'文件|文档|原文', positive)):
        task_type = 'summarize_file'
    elif contract['file']:
        task_type = 'new_document'
    elif re.search(r'搜索|查一下|查询|search', lower):
        task_type = 'search'
    elif re.search(r'[？?]$|什么|哪些|为什么|怎么', positive):
        task_type = 'question'
    else:
        task_type = 'chat'
    kind = 'none'
    if deliverable != 'none' or task_type in ('new_document', 'summarize_file'):
        kind = ('questionnaire' if '问卷' in positive else 'confirmation_letter' if '确认函' in positive else 'checklist' if '清单' in positive
                else 'template' if re.search(r'模板|示例', positive) else 'summary' if task_type == 'summarize_file' else 'plan' if '计划' in positive
                else 'letter' if re.search(r'信|函|邮件', positive) else 'report')
    topic = 'none'
    if realtime_request(text):
        topic = ('crypto_price' if re.search(r'btc|eth|比特币|以太|币价|币安|okx|coinbase', lower) else 'stock' if re.search(r'股价|股票|a股|美股', lower)
                 else 'fx' if '汇率' in positive else 'weather' if '天气' in positive else 'news' if '新闻' in positive else 'crypto_price' if '行情' in positive else 'none')
    symbols = sorted({v for k, v in SYMBOL_WORDS.items() if k in lower and v != 'USDT'})
    platforms = sorted({v for k, v in PLATFORM_ALIASES.items() if k in lower})
    return {'task_type': task_type, 'deliverable': deliverable, 'document_kind': kind, 'needs_realtime': topic != 'none',
            'realtime_topic': topic, 'symbols': symbols, 'platforms': platforms, 'input_files': mentioned,
            'remember': contract['memory'], 'explicit_template': bool(re.search(r'模板|示例', positive)) and template_request(text),
            'confidence': 0.5, 'source': 'rules'}


def reconcile(model, rules, text, listing=()):
    """Deterministic corrections win over the model on everything the program can verify."""
    out = dict(rules)
    if isinstance(model, dict):
        for key in ('task_type', 'document_kind', 'realtime_topic', 'deliverable'):
            if model.get(key) in SCHEMA['properties'][key]['enum']:
                out[key] = model[key]
        if isinstance(model.get('needs_realtime'), bool):
            positive = NEGATED.sub('', text)
            # The model may only claim realtime need when the request actually mentions something time-bound or market-like.
            out['needs_realtime'] = model['needs_realtime'] and (rules['needs_realtime'] or bool(re.search(r'今日|今天|最新|实时|当前|现在|价格|行情|走势|汇率|新闻|天气|股价|币价|多少钱|报价', positive)))
        out['symbols'] = sorted(set(rules['symbols']) | {s.upper() for s in model.get('symbols', []) if isinstance(s, str) and re.fullmatch(r'[A-Za-z]{2,10}', s)})
        out['platforms'] = sorted(set(rules['platforms']) | {PLATFORM_ALIASES.get(p.lower(), p.lower()) for p in model.get('platforms', []) if isinstance(p, str) and re.fullmatch(r'[A-Za-z]{2,20}', p)})
        try:
            out['confidence'] = max(0.0, min(1.0, float(model.get('confidence', 0.5))))
        except (TypeError, ValueError):
            out['confidence'] = 0.5
        out['source'] = 'model'
    contract = requirements(text)
    if contract['file'] and out['task_type'] in ('reminder', 'memory', 'chat', 'question', 'search'):
        out['task_type'] = rules['task_type']
    # A reminder or a memory write needs the user's own words for it; a small model must not "hear" one in a follow-up.
    positive_text = NEGATED.sub('', text)
    if out['task_type'] == 'reminder' and not re.search(r'提醒|闹钟|叫我|喊我|别忘了|记得', positive_text):
        out['task_type'] = rules['task_type'] if rules['task_type'] != 'reminder' else 'chat'
    if out['task_type'] == 'memory' and not contract['memory'] and not re.search(r'记住|记一下|记下|记录|备忘|笔记|记忆', positive_text):
        out['task_type'] = rules['task_type'] if rules['task_type'] != 'memory' else 'chat'
    # Only the user can turn a request into a file: without 生成/保存/写成 + 文档/word/pdf (or a filename) there is no deliverable,
    # whatever the model guessed. A small model happily "upgrades" a greeting into a Word document otherwise.
    if not contract['file'] and not contract['files']:
        out['deliverable'] = 'none'
        if out['task_type'] in ('new_document', 'convert', 'export_conversation'):
            out['task_type'] = rules['task_type'] if rules['task_type'] not in ('new_document', 'convert', 'export_conversation') else 'chat'
    names = {item['path'] for item in listing}
    # A file counts as input only when the user actually named it (full name or stem); the model may not volunteer the whole folder.
    def mentioned(name):
        stem = name.rsplit('.', 1)[0]
        return name in text or (len(stem) >= 2 and stem in text)
    out['input_files'] = [f for f in dict.fromkeys(list(rules['input_files'])+[f for f in (model or {}).get('input_files', []) if isinstance(f, str)]) if f in names and mentioned(f)]
    out['files'] = contract['files']
    out['needs_file'] = bool(contract['file'] or out['deliverable'] != 'none' or out['task_type'] in ('new_document', 'export_conversation'))
    if out['task_type'] in ('chat', 'question', 'memory', 'reminder', 'search') and not contract['file'] and not contract['files']:
        out['needs_file'] = False
        out['deliverable'] = 'none'
    out['needs_memory'] = contract['memory']
    out['needs_reminder'] = contract['reminder']
    out['no_memory'] = contract['no_memory']
    out['no_file'] = bool(re.search(r'(?:不要|不得|禁止|别)[^，。；\n]*(?:保存|生成|写入|创建)[^，。；\n]*(?:文件|文档)', text)) or bool(re.search(r'(?:不要|别|不用)(?:保存|生成)文件', text))
    if out['no_file']:
        out['needs_file'] = False
        out['deliverable'] = 'none'
        if out['task_type'] == 'new_document':
            out['task_type'] = 'summarize_file' if out['input_files'] else 'chat'
    out['explicit_template'] = bool(out.get('explicit_template')) or rules['explicit_template']
    if out['explicit_template'] or template_request(text):
        out['needs_realtime'] = False
    elif realtime_request(text):
        out['needs_realtime'] = True
    if out['needs_realtime'] and out['realtime_topic'] == 'none':
        out['realtime_topic'] = rules['realtime_topic'] if rules['realtime_topic'] != 'none' else 'crypto_price'
    if not out['needs_realtime']:
        out['realtime_topic'] = 'none'
    return out


FIXED_PATTERNS = [
    r'(?:上面|这段|刚才|以上|这些话).{0,12}(?:写成|生成|导出|保存|转)(?:成|为)?\s*(?:一[份个]\s*)?(?:pdf|word|docx)',
    r'^(?:请)?(?:分析|统计|计算)\s*.+?\.(?:csv|tsv|xlsx)\s*.+',
    r'^把\s*.+?\.(?:md|txt|csv|tsv|json|html|log)\s*中的[“"].+?[”"](?:全部)?(?:改成|改为|替换为)[“"].*?[”"]\s*[，,]\s*再(?:转换成|转成|转换为)',
    r'^\d{1,4}\s*(?:分钟|小时)后提醒我',
]


def fixed_workflow_text(text):
    """Fully specified commands the loop executes without any model call."""
    stripped = text.strip()
    for i, p in enumerate(FIXED_PATTERNS):
        if re.search(p, stripped, re.I):
            if i == 1 and re.search(r'保存|生成|写入|趋势|预测|修改|报告', stripped):
                continue  # a stats sentence that also wants a file is a summarize job, not the bare stats reply
            return True
    return False


async def classify(provider, text, listing=(), timeout=90, skip_model=False):
    rules = heuristic(text, listing)
    if skip_model or fixed_workflow_text(text) or not provider.profile.get('supports_schema', True):
        return reconcile(None, rules, text, listing)
    reply = await provider.chat([{'role': 'system', 'content': SYSTEM},
                                 {'role': 'user', 'content': json.dumps({'用户请求': text, '工作目录文件': [i['path'] for i in listing][:40]}, ensure_ascii=False)}],
                                schema=SCHEMA, max_tokens=300, temperature=0, timeout=timeout)
    model = None
    if not reply.failed and reply.content:
        try:
            model = json.loads(reply.content)
        except ValueError:
            model = None
    result = reconcile(model, rules, text, listing)
    result['model_reply'] = None if model else (reply.content[:200] if reply.failed else 'unparsed')
    return result
