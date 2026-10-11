"""Verify the configured Qwen vision model with an explicitly synthetic image."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app import app
from ai import AIError, draft_report

with tempfile.TemporaryDirectory() as directory, app.app_context():
    image = Image.new('RGB', (500, 180), 'white')
    ImageDraw.Draw(image).text((40, 70), 'TEST ONLY - NO CLINICAL DATA', fill='black')
    image.save(Path(directory) / 'test.png')
    app.config['UPLOAD_DIR'] = directory
    case = SimpleNamespace(
        id=0, kind='initial', parent=None, answers=[], triage=None,
        profile_snapshot={'name': '虚构患者', 'age': 30, 'gender': '女', 'allergies': '青霉素', 'history': '无', 'medications': '无'},
        title='虚构视觉接口验收', duration='3 天',
        description='虚构病例：干咳三天，无发热或气促。附件仅为 TEST ONLY 测试图片，无临床资料，请明确这一限制。',
        attachments=[SimpleNamespace(storage_name='test.png', mime='image/png', name='test.png')])
    try:
        content, model = draft_report(case)
    except AIError as exc:
        if getattr(exc.__cause__, 'response', None) is not None:
            print('AI provider diagnostic:', exc.__cause__.response.text[:500])
        raise SystemExit(str(exc))
    print('Vision inference passed:', model, {key: len(str(value)) for key, value in content.items()})
