"""Attachment validation and storage."""
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from flask import current_app
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

from models import Attachment, db
from security import ApiError

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_PER_UPLOAD = 5
MAX_PER_CASE = 20
ALLOWED_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp', '.pdf')


def inspect_upload(upload):
    name = Path(upload.filename or '').name[:200]
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError('附件仅支持 PNG、JPG、WebP 或 PDF 格式')
    data = upload.read(MAX_FILE_SIZE + 1)
    if not data or len(data) > MAX_FILE_SIZE:
        raise ValueError('单个附件必须在 10 MB 以内且不能为空')
    try:
        if suffix == '.pdf':
            if not data.startswith(b'%PDF-'):
                raise ValueError('PDF 文件内容无效')
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise ValueError('请上传未加密的 PDF')
            if len(reader.pages) > 50:
                raise ValueError('PDF 最多支持 50 页')
            mime = 'application/pdf'
        else:
            with Image.open(BytesIO(data)) as img:
                if img.format not in ('PNG', 'JPEG', 'WEBP'):
                    raise ValueError('图片内容与支持格式不符')
                if img.width * img.height > 25_000_000:
                    raise ValueError('图片尺寸过大，请缩小后上传')
                mime = Image.MIME[img.format]
                img.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ValueError('附件损坏或格式无效') from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('无法读取附件，请检查文件') from exc
    return name, suffix, mime, data


def validate_uploads(files, existing=0):
    uploads = [f for f in files if f.filename]
    if len(uploads) > MAX_PER_UPLOAD:
        raise ApiError(f'每次最多上传 {MAX_PER_UPLOAD} 个附件')
    if existing + len(uploads) > MAX_PER_CASE:
        raise ApiError(f'每份病例最多保存 {MAX_PER_CASE} 个附件')
    try:
        return [inspect_upload(upload) for upload in uploads]
    except ValueError as exc:
        raise ApiError(str(exc)) from exc


def store(validated, case_id, user_id, message_id=None, written=None):
    """Write validated files and add rows to the session. ``written`` collects paths
    so the caller can remove them if the transaction rolls back."""
    folder = Path(current_app.config['UPLOAD_DIR'])
    for name, suffix, mime, content in validated:
        storage_name = f'{uuid4().hex}{suffix}'
        path = folder / storage_name
        path.write_bytes(content)
        if written is not None:
            written.append(path)
        db.session.add(Attachment(case_id=case_id, message_id=message_id, uploaded_by=user_id, name=name,
                                  storage_name=storage_name, mime=mime, size=len(content)))
