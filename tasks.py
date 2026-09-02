"""Web task layer — background PPT generation pipeline with progress tracking.

Runs on FastAPI BackgroundTasks rather than Celery: this is a single-user
local tool with no broker (Redis/RabbitMQ) infrastructure, and Starlette
already runs sync background functions in a threadpool so the event loop
stays responsive. Swap to Celery only if we ever go multi-process / multi-host.

Pipeline: read uploads → extract agenda (DeepSeek/OCR) → extract speakers
(DeepSeek) → ppt_generator.generate_ppt → web_output/<task_id>.pptx。
若 options 携带编辑后的 agenda_items/speakers，对应步骤跳过提取、直接用编辑数据。

Tasks and uploads are persisted in the database (tasks/uploads tables), so
they survive server restarts.
"""
import asyncio
import logging
import os
import time
import traceback
import tempfile
import uuid
from pathlib import Path

from database import db

logger = logging.getLogger('pptmaker.tasks')

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / 'data' / 'web_output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Task statuses
PENDING = 'pending'
RUNNING = 'running'
DONE = 'done'
FAILED = 'failed'

# Fields that must never be stored on the task record (returned by /api/status)
_SECRET_FIELDS = ('api_key', 'ocr_api_key')


# ---------------------------------------------------------------------------
# Task registry (DB-backed)
# ---------------------------------------------------------------------------

def create_task(options: dict, user_id: int = None) -> str:
    """Register a new generation task. Returns its task_id."""
    # Sanitize: never keep API keys on the record served by /api/status
    safe_options = {k: v for k, v in options.items() if k not in _SECRET_FIELDS}
    task_id = uuid.uuid4().hex
    db.create_task(task_id, options=safe_options, user_id=user_id)
    logger.info('[%s] 任务已创建 — 日程: %s, 演讲者: %s',
                task_id, options.get('agenda_file_id'),
                options.get('speaker_file_ids'))
    return task_id


def get_task(task_id: str):
    return db.get_task(task_id)


def _update(task_id: str, **fields):
    db.update_task(task_id, **fields)


# ---------------------------------------------------------------------------
# Upload helpers (DB-backed)
# ---------------------------------------------------------------------------

def read_upload(file_id: str) -> bytes:
    """Read an uploaded file's bytes. Raises if the ID is unknown."""
    rec = db.get_upload(file_id)
    if rec is None:
        raise ValueError(f'未知文件ID: {file_id}')
    with open(rec['path'], 'rb') as f:
        return f.read()


def _materialize_upload(file_id) -> tuple:
    """Write an upload to a temp file; returns (path, cleanup_fn).

    Used for background images, which generate_ppt reads from disk paths.
    Returns (None, noop) when file_id is absent (background is optional).
    """
    if not file_id:
        return None, lambda: None
    data = read_upload(file_id)
    rec = db.get_upload(file_id)
    suffix = Path(rec['filename']).suffix.lower() or '.png'
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()
    with open(tmp.name, 'wb') as f:
        f.write(data)
    return tmp.name, lambda: _safe_unlink(tmp.name)


def _safe_unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Generation pipeline (runs inside the BackgroundTasks threadpool)
# ---------------------------------------------------------------------------

def _rebuild_agenda(items):
    """从编辑后的 dict 列表重建 AgendaItem（逐字段容错，仿 _parse_agenda_json）。"""
    from extractors.agenda_extractor import AgendaItem

    agenda = []
    for it in items or []:
        agenda.append(AgendaItem(
            order=int(it.get('order') or 0),
            time_slot=str(it.get('time_slot', '')),
            session_title_cn=str(it.get('session_title_cn', '')),
            session_title_en=str(it.get('session_title_en', '')),
            speaker_name=str(it.get('speaker_name', '')),
            host=str(it.get('host', '')),
            institution=str(it.get('institution', '')),
            item_type=str(it.get('item_type', 'speech')),
        ))
    return agenda


def run_generation_task(task_id: str, options: dict):
    """Full pipeline. Updates the task record with progress; never raises.

    数据来源（可混用）：options['agenda_items'] / options['speakers'] 存在时
    使用用户在前端编辑后的数据重建对象、跳过 AI 提取（无需 api_key）；
    缺省时按原流程从上传文件提取。
    """
    t0 = time.monotonic()
    bg_path, bg_cleanup = None, lambda: None
    content_path, content_cleanup = None, lambda: None
    photo_cleanups = []
    try:
        api_key = options.get('api_key', '')
        ocr_api_key = options.get('ocr_api_key', '')
        _update(task_id, task_status=RUNNING, progress=5, message='准备数据')

        # 1. Agenda — 编辑数据优先，否则从上传文件提取
        if options.get('agenda_items') is not None:
            _update(task_id, progress=20, message='应用编辑后的日程数据')
            agenda_items = _rebuild_agenda(options['agenda_items'])
            logger.info('[%s] 使用编辑后的日程数据: %d 个环节',
                        task_id, len(agenda_items))
        else:
            if not api_key:
                raise RuntimeError('缺少 DeepSeek API Key：请到「账户设置」配置个人 Key，或由管理员配置共享 Key')
            agenda_rec = db.get_upload(options.get('agenda_file_id', '') or '')
            if agenda_rec is None:
                raise ValueError('agenda_file_id 无效或缺失')
            _update(task_id, progress=20, message='正在提取会议日程')
            from extractors.agenda_extractor import extract_agenda
            agenda_items = extract_agenda(
                read_upload(options['agenda_file_id']), api_key, ocr_api_key,
                filename=agenda_rec['filename'])
            logger.info('[%s] 日程提取完成: %d 个环节 (%.1fs)',
                        task_id, len(agenda_items), time.monotonic() - t0)

        # 2. Speakers — 编辑数据优先，否则逐个提取
        if options.get('speakers') is not None:
            _update(task_id, progress=45, message='应用编辑后的演讲者数据')
            from extractors.speaker_extractor import Speaker
            speakers = {}
            for s in options['speakers']:
                name = str(s.get('name', '')).strip()
                if not name:
                    continue
                photo_path = None
                photo_file_id = s.get('photo_file_id') or ''
                if photo_file_id:
                    if db.get_upload(photo_file_id) is None:
                        raise ValueError(f'演讲者「{name}」的照片文件ID无效: {photo_file_id}')
                    photo_path, photo_cleanup = _materialize_upload(photo_file_id)
                    photo_cleanups.append(photo_cleanup)
                speakers[name] = Speaker(
                    name=name,
                    photo_path=photo_path or '',
                    bio=str(s.get('bio', '')),
                    bio_en=str(s.get('bio_en', '')),
                    institution=str(s.get('institution', '')),
                    title=str(s.get('title', '')) or '教授',
                )
            logger.info('[%s] 使用编辑后的演讲者数据: %d 位',
                        task_id, len(speakers))
        else:
            if not api_key:
                raise RuntimeError('缺少 DeepSeek API Key：请到「账户设置」配置个人 Key，或由管理员配置共享 Key')
            speaker_ids = options.get('speaker_file_ids', [])
            _update(task_id, progress=45,
                    message=f'正在提取演讲者信息 (0/{len(speaker_ids)})')
            from extractors.speaker_extractor import extract_speaker
            speakers = {}
            n = len(speaker_ids)
            for i, fid in enumerate(speaker_ids, 1):
                rec = db.get_upload(fid)
                if rec is None:
                    raise ValueError(f'speaker_file_ids 含未知文件ID: {fid}')
                _update(task_id, progress=45 + int(30 * i / n),
                        message=f'正在提取演讲者信息 ({i}/{n})')
                data = read_upload(fid)
                sp = extract_speaker(data, api_key, filename=rec['filename'])
                speakers[sp.name] = sp
                logger.info('[%s] 演讲者提取完成: %s (%.1fs)',
                            task_id, sp.name, time.monotonic() - t0)

        # 4. Build the PPT
        _update(task_id, progress=85, message='正在生成PPT页面')
        bg_path, bg_cleanup = _materialize_upload(options.get('home_bg_file_id'))
        content_path, content_cleanup = _materialize_upload(options.get('content_bg_file_id'))
        if not bg_path:
            logger.warning('[%s] 未提供首页背景图，封面将无背景', task_id)
        if not content_path:
            logger.warning('[%s] 未提供内容页背景图，内容页将无背景', task_id)

        from ppt_generator import generate_ppt
        output_path = str(OUTPUT_DIR / f'{task_id}.pptx')
        generate_ppt(
            agenda_items=agenda_items,
            speakers=speakers,
            home_bg=bg_path or '',
            content_bg=content_path or '',
            slide_size=options.get('slide_size', '16:9'),
            lang=options.get('lang', 'bilingual'),
            output_path=output_path,
        )

        _update(task_id, task_status=DONE, progress=100, message='生成完成',
                pptx_path=output_path)
        logger.info('[%s] 生成完成: %s (总耗时 %.1fs)',
                    task_id, output_path, time.monotonic() - t0)
    except Exception as e:
        logger.exception('[%s] 生成失败: %s', task_id, e)
        _update(task_id, task_status=FAILED, message=f'生成失败: {e}',
                error=traceback.format_exc())
    finally:
        bg_cleanup()
        content_cleanup()
        for photo_cleanup in photo_cleanups:
            photo_cleanup()


# ---------------------------------------------------------------------------
# Async wrapper around the sync core generator (for asyncio contexts)
# ---------------------------------------------------------------------------

async def generate_ppt_async(agenda_items, speakers, home_bg, content_bg,
                             slide_size, lang, output_path):
    """Async wrapper: runs the CPU-bound ppt_generator.generate_ppt in a
    worker thread so the event loop is never blocked."""
    from ppt_generator import generate_ppt
    return await asyncio.to_thread(
        generate_ppt, agenda_items, speakers, home_bg, content_bg,
        slide_size, lang, output_path)
