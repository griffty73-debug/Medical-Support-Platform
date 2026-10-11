"""Published report as a PDF with an embedded Chinese font."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from workflow import REPORT_LABELS, REPORT_TEXT_FIELDS, TZ, VISIT_LABELS

INK = colors.HexColor('#1d232b')
MUTED = colors.HexColor('#5d6670')
ACCENT = colors.HexColor('#24439a')


def _font():
    if 'NotoSansSC' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('NotoSansSC', str(Path(__file__).parent / 'assets' / 'NotoSansSC-Regular.ttf')))


def _styles():
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = 'NotoSansSC'
        style.leading = 19
        style.wordWrap = 'CJK'
        style.textColor = INK
    styles['Title'].fontSize = 20
    styles['Title'].leading = 28
    styles['Heading2'].fontSize = 12.5
    styles['Heading2'].spaceBefore = 16
    styles['Heading2'].spaceAfter = 4
    styles['Heading2'].textColor = ACCENT
    styles['BodyText'].fontSize = 10.5
    styles['Italic'].fontSize = 9
    styles['Italic'].textColor = MUTED
    return styles


def _date(value):
    return value.astimezone(TZ).strftime('%Y-%m-%d %H:%M') if value else ''


def report_pdf(case):
    _font()
    styles = _styles()
    stream = BytesIO()
    number = f'MP-{case.id:06d}'
    document = SimpleDocTemplate(stream, title=f'诊疗评估报告 {number}', author='医疗平台',
                                 leftMargin=52, rightMargin=52, topMargin=52, bottomMargin=56)
    profile = case.profile_snapshot
    report = case.report
    body = [Paragraph('诊疗评估报告', styles['Title']), Spacer(1, 4)]
    edition = f'第 {case.published_version} 版' if case.published_version > 1 else '首次发布'
    rows = [
        ['报告编号', number, '就诊类型', '复诊' if case.kind == 'followup' else '初诊'],
        ['姓名', profile['name'], '年龄 / 性别', f'{profile["age"]} 岁 / {profile["gender"]}'],
        ['审核医生', f'{case.doctor.name}  {case.doctor.title or ""}', '科室', case.doctor.department or ''],
        ['发布时间', _date(case.amended_at or case.published_at), '版本', edition],
    ]
    meta = Table([[Paragraph(escape(str(v)), styles['BodyText']) for v in row] for row in rows],
                 colWidths=[62, 170, 66, 193])
    meta.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'NotoSansSC'), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TEXTCOLOR', (0, 0), (0, -1), MUTED), ('TEXTCOLOR', (2, 0), (2, -1), MUTED),
        ('LINEABOVE', (0, 0), (-1, 0), 1.2, INK), ('LINEBELOW', (0, -1), (-1, -1), 0.6, INK),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    body.extend([meta, Spacer(1, 10), Paragraph('主诉：' + escape(case.title), styles['Heading2'])])
    for field in REPORT_TEXT_FIELDS:
        body.append(Paragraph(REPORT_LABELS[field], styles['Heading2']))
        body.append(Paragraph(escape(report.get(field, '')).replace('\n', '<br/>'), styles['BodyText']))
    if report.get('visit'):
        body.append(Paragraph('线下就诊建议', styles['Heading2']))
        body.append(Paragraph(escape(VISIT_LABELS[report['visit']]), styles['BodyText']))
    if report.get('followup_days'):
        due = case.followup_due.strftime('%Y-%m-%d') if case.followup_due else ''
        body.append(Paragraph('随访安排', styles['Heading2']))
        body.append(Paragraph(f'建议 {report["followup_days"]} 天后（{due} 前后）复诊，期间症状加重请及时就医。', styles['BodyText']))
    if case.published_version > 1 and case.status_reason:
        body.extend([Spacer(1, 8), Paragraph('更正说明：' + escape(case.status_reason), styles['Italic'])])
    body.extend([Spacer(1, 24),
                 Paragraph(f'审核医生：{escape(case.doctor.name)}　{escape(case.doctor.title or "")}', styles['BodyText']),
                 Spacer(1, 6),
                 Paragraph('本报告基于患者线上提交的资料形成，不能替代线下面诊与必要检查。如出现急症，请立即拨打 120 或前往急诊。',
                           styles['Italic'])])

    def page_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('NotoSansSC', 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(52, 30, f'医疗平台　{number}　{edition}')
        canvas.drawRightString(doc.pagesize[0] - 52, 30, f'第 {doc.page} 页')
        canvas.restoreState()

    document.build(body, onFirstPage=page_footer, onLaterPages=page_footer)
    stream.seek(0)
    return stream
