"""Pre-consultation triage.

Deterministic red-flag rules always run, need no third-party processing and
cannot be switched off. The optional AI pre-consultation adds follow-up
questions, a suggested department and a summary for the doctor; its urgency can
only raise, never lower, the level found by the rules.
"""
import hashlib
import re

# (pattern, level, label, what the patient should do)
RULES = [
    (r'胸痛|胸口(痛|疼)|心前区(痛|疼)|压榨(样|性)(痛|疼)', 'emergency', '胸痛',
     '胸痛可能与心脏或大血管急症有关，请立即拨打 120 或前往急诊。'),
    (r'呼吸困难|喘不(上|过)气|憋气|窒息|呼吸急促', 'emergency', '呼吸困难',
     '呼吸困难需要尽快评估，请立即拨打 120 或前往急诊。'),
    (r'意识(不清|模糊|丧失)|昏迷|晕厥|昏倒|晕倒|叫不醒', 'emergency', '意识障碍',
     '出现意识改变或晕厥，请立即拨打 120。'),
    (r'抽搐|癫痫发作|四肢抽动', 'emergency', '抽搐', '正在或刚发生抽搐，请立即拨打 120。'),
    (r'口角歪斜|口眼歪斜|言语不清|说话不清|口齿不清|(一侧|半边|单侧)(肢体|手脚|身体|胳膊|腿)?(无力|麻木|不能动)', 'emergency',
     '疑似脑卒中表现', '卒中救治有时间窗，请立即拨打 120，并记录症状出现的时间。'),
    (r'呕血|吐血|咯血|大出血|出血不止|黑便|柏油样便', 'emergency', '出血',
     '活动性出血需要急诊处理，请立即就医。'),
    (r'(剧烈|爆炸样|炸裂样|一生中最严重的)头痛', 'emergency', '突发剧烈头痛',
     '突发剧烈头痛需排除颅内出血，请立即前往急诊。'),
    (r'喉咙肿|喉头水肿|嘴唇肿|舌头肿|过敏性休克', 'emergency', '严重过敏反应',
     '可能是严重过敏反应，请立即拨打 120。'),
    (r'(怀孕|孕期|妊娠|孕妇|孕\d+周).{0,12}(出血|流血|腹痛|肚子痛)', 'emergency', '孕期出血或腹痛',
     '孕期出血或腹痛需要尽快由产科评估，请立即就医。'),
    (r'自杀|轻生|不想活|结束(自己的)?生命|伤害自己|自残|割腕', 'crisis', '心理危机',
     '你不必独自面对。请立即拨打心理援助热线 12356，或在危险时拨打 110 / 120，并联系身边可信任的人陪伴你。'),
    (r'高(烧|热)|(发烧|发热|体温)\D{0,4}(39|4[0-2])(\.\d)?|(39|4[0-2])(\.\d)?\s*(度|℃)', 'urgent', '高热',
     '高热需要尽快评估，如伴精神差、皮疹或呼吸急促请立即就医。'),
    (r'剧烈(腹痛|肚子痛|疼痛)|疼得(受不了|打滚|睡不着)|痛得(受不了|打滚)', 'urgent', '剧烈疼痛',
     '剧烈疼痛需要尽快就医明确原因。'),
    (r'持续(呕吐|吐)|吐个不停|喝水都吐|无法进食', 'urgent', '持续呕吐',
     '持续呕吐可能导致脱水，请尽快就医。'),
    (r'骨折|外伤后.{0,4}(肿胀|畸形|不能动)|摔伤|撞伤', 'urgent', '外伤',
     '外伤后如肿胀明显、畸形或无法活动，请尽快就医拍片。'),
    (r'血尿|尿血|无尿|尿不出', 'urgent', '泌尿异常', '请尽快就医检查。'),
    (r'(突然|骤然).{0,4}(看不清|视力下降|失明)|视物重影', 'urgent', '视力突变', '视力突然变化请尽快到眼科或急诊就诊。'),
]
_COMPILED = [(re.compile(pattern), level, label, advice) for pattern, level, label, advice in RULES]
_NEGATION = re.compile(r'(无|没有|没|否认|未见|未出现|未|不伴有?|不)(明显的?|任何)?$')
_HISTORY = re.compile(r'(既往|以前|之前|曾经?|多年前|去年|小时候)[^，。,；;！!？?]{0,4}$')


def _negated(text, start):
    """True when the match is denied ("无胸痛") or describes past history ("既往骨折")."""
    before = re.sub(r'\s+', '', text[max(0, start - 10):start])
    return bool(_NEGATION.search(before) or _HISTORY.search(before))


def rule_flags(text):
    flags, seen = [], set()
    for pattern, level, label, advice in _COMPILED:
        if label in seen:
            continue
        for match in pattern.finditer(text):
            if not _negated(text, match.start()):
                flags.append({'label': label, 'level': level, 'advice': advice, 'evidence': match.group(0)})
                seen.add(label)
                break
    return flags


def level_of(flags):
    levels = {('emergency' if f['level'] == 'crisis' else f['level']) for f in flags}
    return 'emergency' if 'emergency' in levels else 'urgent' if 'urgent' in levels else 'routine'


def fingerprint(title, description, duration):
    return hashlib.sha256('\x1f'.join((title.strip(), description.strip(), duration.strip())).encode()).hexdigest()


def assess(title, description, duration='', answers=None):
    text = '\n'.join([title, description, duration] + [a.get('a', '') for a in (answers or [])])
    flags = rule_flags(text)
    return {'level': level_of(flags), 'flags': flags}
