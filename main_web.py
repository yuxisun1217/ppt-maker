"""Web backend for the conference PPT generator — FastAPI.

Serves the web frontend (web/web_prototype.html) and drives the same
extraction/generation pipeline as the desktop app via tasks.py.
"""
import base64
import logging
import logging.handlers
import os
import sys
import time
import uuid
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Optional

# Ensure project root is on path so extractors/ and ppt_generator import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import (BackgroundTasks, Depends, FastAPI, File, HTTPException,
                     Request, Response, UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import tasks
from database import db
from extractors.ppt_background import extract_backgrounds

# ---------------------------------------------------------------------------
# Logging — console + rotating file, one log for everything in this project
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

_console = logging.StreamHandler()
_file = logging.handlers.RotatingFileHandler(
    LOG_DIR / 'web_backend.log', maxBytes=2 * 1024 * 1024, backupCount=3,
    encoding='utf-8')
_fmt = logging.Formatter('%(asctime)s %(levelname)-7s %(name)s: %(message)s')
for h in (_console, _file):
    h.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_console, _file])
# Silence noisy third-party loggers
for noisy in ('uvicorn.access', 'PIL', 'urllib3'):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger('pptmaker.web')

UPLOAD_DIR = BASE_DIR / 'data' / 'web_uploads'
OUTPUT_DIR = BASE_DIR / 'data' / 'web_output'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Uploads and tasks are persisted in the DB (uploads/tasks tables).
db.init_db()
promoted = db.ensure_admin()
if promoted:
    logger.warning('未检测到管理员账户，已将最早注册的用户「%s」设为管理员', promoted)

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------

app = FastAPI(title="会议串场 PPT 生成器 Web API", version="0.1.0")

# Local tool: allow the same-origin server hosts plus file:// ("null") so the
# prototype can also be opened directly from disk. Cookie auth requires
# allow_credentials=True, which forbids a wildcard origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://127.0.0.1:8000', 'http://localhost:8000', 'null'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.middleware('http')
async def log_requests(request: Request, call_next):
    t0 = time.monotonic()
    response = await call_next(request)
    logger.info('%s %s -> %d (%.1fms)', request.method, request.url.path,
                response.status_code, (time.monotonic() - t0) * 1000)
    return response


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    agenda_file_id: str = Field(..., description='日程文件ID，来自 /api/upload')
    speaker_file_ids: list[str] = Field(default_factory=list,
                                        description='演讲者资料文件ID列表')
    api_key: str = Field(default='', description='DeepSeek API Key（账号已配置时可省略，服务端按账号读取）')
    ocr_api_key: str = Field(default='', description='OCR.space API Key（日程为图片时需要）')
    home_bg_file_id: Optional[str] = Field(default=None, description='首页/章节背景图文件ID（可选）')
    content_bg_file_id: Optional[str] = Field(default=None, description='内容页背景图文件ID（可选）')
    slide_size: str = Field(default='16:9', description="'16:9' 或 'ultrawide'")
    lang: str = Field(default='bilingual', description="'bilingual' 或 'chinese'")
    agenda_items: Optional[list[dict]] = Field(default=None, description='编辑后的日程数据（提供后跳过日程提取）')
    speakers: Optional[list[dict]] = Field(default=None, description='编辑后的演讲者数据（提供后跳过演讲者提取）')


class ParseRequest(BaseModel):
    """AI 解析日程/演讲者资料请求。"""
    agenda_file_id: str = Field(..., description='日程文件ID，来自 /api/upload')
    speaker_file_ids: list[str] = Field(default_factory=list,
                                        description='演讲者资料文件ID列表')
    api_key: str = Field(default='', description='DeepSeek API Key（账号已配置时可省略，服务端按账号读取）')
    ocr_api_key: str = Field(default='', description='OCR.space API Key（日程为图片时需要）')


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)


class CreateUserRequest(BaseModel):
    """Admin creates an account."""
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    is_admin: bool = False


class ResetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=4, max_length=128)


class SetAdminRequest(BaseModel):
    is_admin: bool


class AccountKeysRequest(BaseModel):
    api_key: str = ''
    ocr_api_key: str = ''


# ---------------------------------------------------------------------------
# Web auth — cookie sessions (in-memory; server restart requires re-login)
# ---------------------------------------------------------------------------

_SESSION_COOKIE = 'pptmaker_session'
_SESSION_TTL = 7 * 24 * 3600  # 7 天
_SESSIONS: dict[str, int] = {}  # token -> user_id


def _set_session(response: Response, user_id: int) -> str:
    token = uuid.uuid4().hex
    _SESSIONS[token] = user_id
    response.set_cookie(_SESSION_COOKIE, token, httponly=True,
                        samesite='lax', max_age=_SESSION_TTL, path='/')
    return token


def _drop_session(request: Request, response: Response):
    token = request.cookies.get(_SESSION_COOKIE)
    if token:
        _SESSIONS.pop(token, None)
    response.delete_cookie(_SESSION_COOKIE, path='/')


def _drop_user_sessions(user_id: int):
    """Invalidate all sessions of a user (after password reset / deletion)."""
    for token, uid in list(_SESSIONS.items()):
        if uid == user_id:
            _SESSIONS.pop(token, None)


def _extract_token(request: Request) -> Optional[str]:
    """Session token: X-Session-Token header first (survives cross-host /
    file:// where SameSite cookies aren't sent), cookie as fallback."""
    token = request.headers.get('X-Session-Token')
    if not token:
        token = request.cookies.get(_SESSION_COOKIE)
    return token or None


def _current_user(request: Request) -> Optional[dict]:
    token = _extract_token(request)
    user_id = _SESSIONS.get(token) if token else None
    return db.get_user(user_id) if user_id else None


def _public_user(u: dict) -> dict:
    """User dict safe to send to the browser — no keys, no hashes."""
    return {'id': u['id'], 'username': u['username'],
            'is_admin': u.get('is_admin', False),
            'api_key_configured': bool((u.get('api_key') or '').strip()),
            'ocr_key_configured': bool((u.get('ocr_api_key') or '').strip())}


def require_user(request: Request) -> dict:
    u = _current_user(request)
    if u is None:
        raise HTTPException(status_code=401, detail='未登录，请先登录')
    return u


def require_admin(request: Request) -> dict:
    u = require_user(request)
    if not u.get('is_admin'):
        raise HTTPException(status_code=403, detail='需要管理员权限')
    return u


@app.post("/api/register")
async def register(req: RegisterRequest, response: Response):
    """Create an account and log it in. The very first account becomes admin."""
    username = req.username.strip()
    is_first = not db.list_users()
    user_id = db.create_user(username, req.password)
    if user_id is None:
        raise HTTPException(status_code=409, detail='用户名已存在')
    if is_first:
        db.set_admin(user_id, True)
        logger.info('首个注册账户「%s」已自动设为管理员', username)
    token = _set_session(response, user_id)
    return {'user': _public_user(db.get_user(user_id)), 'token': token}


@app.post("/api/login")
async def login(req: LoginRequest, response: Response):
    u = db.authenticate(req.username, req.password)
    if u is None:
        raise HTTPException(status_code=401, detail='用户名或密码错误')
    token = _set_session(response, u['id'])
    logger.info('用户登录: %s', u['username'])
    return {'user': _public_user(u), 'token': token}


@app.post("/api/logout")
async def logout(request: Request, response: Response):
    _drop_session(request, response)
    return {'ok': True}


@app.get("/api/me")
async def me(user: dict = Depends(require_user)):
    return {'user': _public_user(user)}


@app.post("/api/account/keys")
async def save_account_keys(req: AccountKeysRequest,
                            user: dict = Depends(require_user)):
    """Save the user's own API keys to their account (server-side)."""
    db.update_api_key(user['id'], req.api_key)
    db.update_ocr_api_key(user['id'], req.ocr_api_key)
    return {'ok': True}


# ---------------------------------------------------------------------------
# Admin endpoints — account management
# ---------------------------------------------------------------------------

@app.get("/api/users")
async def list_users(admin: dict = Depends(require_admin)):
    return {'users': db.list_users()}


@app.post("/api/users")
async def create_user(req: CreateUserRequest,
                      admin: dict = Depends(require_admin)):
    user_id = db.create_user(req.username.strip(), req.password)
    if user_id is None:
        raise HTTPException(status_code=409, detail='用户名已存在')
    if req.is_admin:
        db.set_admin(user_id, True)
    logger.info('管理员 %s 创建账户: %s', admin['username'], req.username.strip())
    return {'user': _public_user(db.get_user(user_id))}


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    if user_id == admin['id']:
        raise HTTPException(status_code=400, detail='不能删除当前登录的账户')
    if not db.delete_user(user_id):
        raise HTTPException(status_code=404, detail='用户不存在')
    _drop_user_sessions(user_id)
    logger.info('管理员 %s 删除账户 id=%s', admin['username'], user_id)
    return {'ok': True}


@app.post("/api/users/{user_id}/password")
async def reset_user_password(user_id: int, req: ResetPasswordRequest,
                              admin: dict = Depends(require_admin)):
    if db.get_user(user_id) is None:
        raise HTTPException(status_code=404, detail='用户不存在')
    db.update_password(user_id, req.password)
    _drop_user_sessions(user_id)
    logger.info('管理员 %s 重置账户 id=%s 的密码', admin['username'], user_id)
    return {'ok': True}


@app.post("/api/users/{user_id}/admin")
async def set_user_admin(user_id: int, req: SetAdminRequest,
                         admin: dict = Depends(require_admin)):
    if user_id == admin['id'] and not req.is_admin:
        raise HTTPException(status_code=400, detail='不能取消自己的管理员权限')
    if not db.set_admin(user_id, req.is_admin):
        raise HTTPException(status_code=404, detail='用户不存在')
    return {'ok': True}


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...),
                 user: dict = Depends(require_user)):
    """Save uploaded files (agenda image/docs, speaker docs, backgrounds)."""
    saved = []
    for f in files:
        file_id = uuid.uuid4().hex
        suffix = Path(f.filename or '').suffix.lower()
        dest = UPLOAD_DIR / f'{file_id}{suffix}'
        with dest.open('wb') as out:
            shutil.copyfileobj(f.file, out)
        db.create_upload(file_id, f.filename or '', str(dest),
                         dest.stat().st_size, user_id=user['id'])
        logger.info('收到上传: %s (%d bytes, id=%s)',
                    f.filename, dest.stat().st_size, file_id)
        saved.append({'file_id': file_id, 'filename': f.filename or '',
                      'size': dest.stat().st_size})
    return {'files': saved}


@app.get("/api/upload/{file_id}")
async def get_upload_file(file_id: str, user: dict = Depends(require_user)):
    """取回上传文件的原始内容（用于「查看完整照片」等场景），仅限文件所有者。"""
    rec = db.get_upload(file_id)
    if rec is None:
        raise HTTPException(status_code=404, detail='未知文件ID')
    if rec.get('user_id') is None or rec.get('user_id') != user['id']:
        raise HTTPException(status_code=403, detail='无权访问该文件')
    if not os.path.exists(rec['path']):
        raise HTTPException(status_code=404, detail='文件不存在（可能已被清理）')
    return FileResponse(rec['path'], filename=rec['filename'])


_MAX_TEMPLATE_SIZE = 100 * 1024 * 1024

# 演讲者照片可能的扩展名 → dataURL MIME（extract_speaker 可产出 jpg/png/gif/bmp）
_PHOTO_MIME = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.gif': 'image/gif', '.bmp': 'image/bmp',
}


@app.post("/api/template/background")
async def template_background(file: UploadFile = File(...),
                              user: dict = Depends(require_user)):
    """从上传的 .pptx 模版提取首页/内容页背景图，落盘并登记 uploads 表。"""
    name = file.filename or ''
    if not name.lower().endswith('.pptx'):
        raise HTTPException(400, '请上传 .pptx 模版；旧版 .ppt 请先另存为 .pptx')
    data = await file.read()
    if len(data) > _MAX_TEMPLATE_SIZE:
        raise HTTPException(400, '模版文件过大（超过 100MB）')
    try:
        images = extract_backgrounds(data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    stem = Path(name).stem
    out = {}
    for slot, (img, ext) in images.items():
        label = '首页' if slot == 'home' else '内容页'
        file_id = uuid.uuid4().hex
        dest = UPLOAD_DIR / ('%s.%s' % (file_id, ext))
        with dest.open('wb') as f:
            f.write(img)
        filename = '%s_%s.%s' % (stem, label, ext)
        db.create_upload(file_id, filename, str(dest), dest.stat().st_size,
                         user_id=user['id'])
        mime = 'image/jpeg' if ext in ('jpg', 'jpeg') else 'image/png'
        out[slot] = {
            'file_id': file_id,
            'filename': filename,
            'size': dest.stat().st_size,
            'preview': 'data:%s;base64,%s' % (mime, base64.b64encode(img).decode()),
        }
    logger.info('模版背景提取: %s (home=%s, content=%s)',
                name, out.get('home', {}).get('file_id'),
                out.get('content', {}).get('file_id'))
    return out


@app.post("/api/parse")
def parse_materials(req: ParseRequest, user: dict = Depends(require_user)):
    """AI 解析日程与演讲者资料，返回可编辑的结构化结果。

    同步端点（FastAPI 自动放入线程池执行）：解析需多次 DeepSeek 调用，
    可能耗时数分钟，不会阻塞事件循环。解析出的演讲者照片落盘
    web_uploads 并登记 uploads 表，前端可用 file_id 直接引用/替换。
    """
    from extractors.agenda_extractor import extract_agenda
    from extractors.speaker_extractor import extract_speaker

    # 服务端按账号读取 API Key：账号已配置时优先，否则回退请求中携带的 Key
    api_key = user.get('api_key') or req.api_key
    ocr_api_key = user.get('ocr_api_key') or req.ocr_api_key
    if not api_key:
        raise HTTPException(400, '缺少 DeepSeek API Key，请先到「账户设置」中配置')

    agenda_rec = db.get_upload(req.agenda_file_id)
    if agenda_rec is None:
        raise HTTPException(400, '日程文件不存在，请重新上传')
    try:
        agenda = extract_agenda(tasks.read_upload(req.agenda_file_id),
                                api_key, ocr_api_key,
                                filename=agenda_rec['filename'])
    except Exception as e:
        logger.exception('日程解析失败: %s', e)
        raise HTTPException(400, f'日程解析失败: {e}')

    speakers = []
    for i, fid in enumerate(req.speaker_file_ids, 1):
        rec = db.get_upload(fid)
        if rec is None:
            raise HTTPException(400, f'第 {i} 个演讲者文件不存在，请重新上传')
        try:
            sp = extract_speaker(tasks.read_upload(fid), api_key,
                                 filename=rec['filename'])
        except Exception as e:
            logger.exception('演讲者解析失败: %s', e)
            raise HTTPException(400, f'演讲者解析失败（{rec["filename"]}）: {e}')

        # 照片落盘持久化（extract_speaker 的照片在进程级临时目录，不持久化）
        photo = None

        def _persist_photo(src_path, label):
            """照片落盘并登记 uploads 表。返回 (file_id, filename, mime, bytes)，失败返回 None。"""
            ext = Path(src_path).suffix.lower()
            if ext not in _PHOTO_MIME:
                ext = '.png'
            mime = _PHOTO_MIME[ext]
            try:
                with open(src_path, 'rb') as f:
                    img = f.read()
            except OSError:
                return None
            if not img:
                return None
            file_id = uuid.uuid4().hex
            dest = UPLOAD_DIR / ('%s.%s' % (file_id, ext.lstrip('.')))
            with dest.open('wb') as f:
                f.write(img)
            filename = '%s_%s%s' % (sp.name or '演讲者', label, ext)
            db.create_upload(file_id, filename, str(dest),
                             dest.stat().st_size, user_id=user['id'])
            return file_id, filename, mime, img

        if sp.photo_path and os.path.exists(sp.photo_path):
            saved = _persist_photo(sp.photo_path, '照片')
            if saved:
                file_id, filename, mime, img = saved
                photo = {
                    'file_id': file_id,
                    'filename': filename,
                    'preview': 'data:%s;base64,%s' % (
                        mime, base64.b64encode(img).decode()),
                    'original_file_id': '',
                    'original_filename': '',
                }
                # 裁剪前的完整照片一并落盘，前端点头像可查看
                orig = getattr(sp, 'photo_original_path', '') or ''
                if orig and orig != sp.photo_path and os.path.exists(orig):
                    original = _persist_photo(orig, '完整照片')
                    if original:
                        photo['original_file_id'] = original[0]
                        photo['original_filename'] = original[1]
        speakers.append({
            'name': sp.name,
            'title': sp.title,
            'institution': sp.institution,
            'bio': sp.bio,
            'bio_en': sp.bio_en,
            'photo': photo,
        })

    logger.info('资料解析完成: 日程 %d 个环节, 演讲者 %d 位',
                len(agenda), len(speakers))
    return {'agenda': [asdict(a) for a in agenda], 'speakers': speakers}


@app.post("/api/generate")
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks,
                   user: dict = Depends(require_user)):
    """Trigger PPT generation; returns a task ID for polling."""
    options = req.model_dump()
    # 服务端按账号读取 API Key：账号已配置时优先，否则回退请求中携带的 Key
    if user.get('api_key'):
        options['api_key'] = user['api_key']
    if user.get('ocr_api_key'):
        options['ocr_api_key'] = user['ocr_api_key']
    task_id = tasks.create_task(options, user_id=user['id'])
    background_tasks.add_task(tasks.run_generation_task, task_id, options)
    return {'task_id': task_id, 'status': tasks.PENDING}


@app.get("/api/status/{task_id}")
async def status(task_id: str, user: dict = Depends(require_user)):
    """Return generation progress for a task."""
    task = tasks.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail='未知任务ID')
    if task.get('user_id') != user['id']:
        raise HTTPException(status_code=403, detail='无权访问该任务')
    return task


@app.get("/api/download/{task_id}")
async def download(task_id: str, user: dict = Depends(require_user)):
    """Download the generated PPT file."""
    task = tasks.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail='未知任务ID')
    if task.get('user_id') != user['id']:
        raise HTTPException(status_code=403, detail='无权访问该任务')
    if task['task_status'] != tasks.DONE or not task.get('pptx_path'):
        raise HTTPException(status_code=409, detail='PPT尚未生成完成')
    return FileResponse(task['pptx_path'], filename=f'串场PPT_{task_id[:8]}.pptx')


# ---------------------------------------------------------------------------
# Static frontend (single-file SPA) — open http://127.0.0.1:8000/ in a browser
# ---------------------------------------------------------------------------

app.mount('/web', StaticFiles(directory=str(BASE_DIR / 'web')), name='web')


@app.get('/')
async def index():
    # 访问 Web UI 首先进入登录页；已登录用户由登录页自动跳转主页
    return RedirectResponse(url='/web/login.html')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
