"""文件上传（PDF / 图片 / ZIP 交付件）。"""

from __future__ import annotations

import mimetypes
import re
import uuid
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from intern_platform.config import DATA_ROOT
from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import (
    AuthUser,
    _bearer,
    decode_token,
    get_current_user,
    load_user_roles,
)
from intern_platform.models.user import User
from sqlalchemy.orm import Session

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOAD_ROOT = DATA_ROOT / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_ZIP_BYTES = 100 * 1024 * 1024
MAX_VIDEO_BYTES = 40 * 1024 * 1024
MAX_FILE_BYTES = 20 * 1024 * 1024
_CHUNK = 1024 * 64
FILE_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".zip"}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
IMAGE_MAGIC = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"RIFF", ".webp"),
)


class UploadOut(BaseModel):
    url: str
    filename: str
    size: int


def _safe_name(name: str, *, force_ext: str | None = None) -> str:
    base = Path(name or "file").name
    base = re.sub(r"[^\w.\-]+", "_", base)
    if force_ext:
        stem = Path(base).stem or "file"
        base = f"{stem}{force_ext}"
    return base[:120]


def _detect_image_ext(raw: bytes, filename: str) -> str | None:
    for magic, ext in IMAGE_MAGIC:
        if raw.startswith(magic):
            if ext == ".webp":
                if len(raw) >= 12 and raw[8:12] == b"WEBP":
                    return ".webp"
                continue
            return ext
    suf = Path((filename or "").lower()).suffix
    if suf in IMAGE_EXTS:
        return suf
    return None


async def _stream_upload(
    file: UploadFile,
    *,
    auth_id: int,
    stored_name: str,
    max_bytes: int,
    oversize_detail: str,
    validate_head: Callable[[bytes], str | None] | None = None,
) -> UploadOut:
    """分块落盘，避免整文件进内存；超限或校验失败时清理临时文件。"""
    user_dir = UPLOAD_ROOT / f"u{auth_id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / stored_name
    tmp = path.with_suffix(path.suffix + ".part")
    size = 0
    head = b""
    try:
        with tmp.open("wb") as out:
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=400, detail=oversize_detail)
                if len(head) < 16:
                    need = 16 - len(head)
                    head += chunk[:need]
                    if len(head) >= 16 and validate_head is not None:
                        err = validate_head(head)
                        if err:
                            raise HTTPException(status_code=400, detail=err)
                out.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="文件为空")
        if validate_head is not None and len(head) < 16:
            err = validate_head(head)
            if err:
                raise HTTPException(status_code=400, detail=err)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return UploadOut(
        url=f"/api/v1/uploads/files/u{auth_id}/{stored_name}",
        filename=file.filename or stored_name,
        size=size,
    )


@router.post("/pdf", response_model=UploadOut)
async def upload_pdf(
    file: UploadFile = File(...),
    auth: AuthUser = Depends(get_current_user),
) -> UploadOut:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")
    stored = f"{uuid.uuid4().hex[:12]}_{_safe_name(file.filename, force_ext='.pdf')}"

    def _pdf_head(head: bytes) -> str | None:
        if not head.startswith(b"%PDF"):
            return "文件不是有效 PDF"
        return None

    out = await _stream_upload(
        file,
        auth_id=auth.id,
        stored_name=stored,
        max_bytes=MAX_PDF_BYTES,
        oversize_detail="PDF 不能超过 8MB",
        validate_head=_pdf_head,
    )
    return UploadOut(url=out.url, filename=file.filename, size=out.size)


@router.post("/image", response_model=UploadOut)
async def upload_image(
    file: UploadFile = File(...),
    auth: AuthUser = Depends(get_current_user),
) -> UploadOut:
    # 图片需根据 magic 定扩展名：先缓冲头再流式写入
    head = await file.read(16)
    if not head:
        raise HTTPException(status_code=400, detail="文件为空")
    ext = _detect_image_ext(head, file.filename or "")
    if not ext:
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG / WebP / GIF")
    user_dir = UPLOAD_ROOT / f"u{auth.id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex[:12]}_{_safe_name(file.filename or f'image{ext}', force_ext=ext)}"
    path = user_dir / stored
    tmp = path.with_suffix(path.suffix + ".part")
    size = len(head)
    try:
        with tmp.open("wb") as out:
            out.write(head)
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise HTTPException(status_code=400, detail="图片不能超过 5MB")
                out.write(chunk)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return UploadOut(url=f"/api/v1/uploads/files/u{auth.id}/{stored}", filename=file.filename or stored, size=size)


@router.post("/video", response_model=UploadOut)
async def upload_video(
    file: UploadFile = File(...),
    auth: AuthUser = Depends(get_current_user),
) -> UploadOut:
    name = (file.filename or "").lower()
    if not name.endswith((".mp4", ".webm")):
        raise HTTPException(status_code=400, detail="仅支持 MP4 / WebM")
    ext = ".webm" if name.endswith(".webm") else ".mp4"
    stored = f"{uuid.uuid4().hex[:12]}_video{ext}"
    return await _stream_upload(
        file,
        auth_id=auth.id,
        stored_name=stored,
        max_bytes=MAX_VIDEO_BYTES,
        oversize_detail="视频不能超过 40MB",
    )


@router.post("/file", response_model=UploadOut)
async def upload_file(
    file: UploadFile = File(...),
    auth: AuthUser = Depends(get_current_user),
) -> UploadOut:
    name = file.filename or ""
    ext = Path(name).suffix.lower()
    if ext not in FILE_EXTS:
        raise HTTPException(status_code=400, detail="仅支持 PDF、Word、Excel、PPT、TXT、CSV、ZIP")
    stored = f"{uuid.uuid4().hex[:12]}_{_safe_name(name, force_ext=ext)}"
    out = await _stream_upload(
        file,
        auth_id=auth.id,
        stored_name=stored,
        max_bytes=MAX_FILE_BYTES,
        oversize_detail="文件不能超过 20MB",
    )
    return UploadOut(url=out.url, filename=name or stored, size=out.size)


@router.post("/zip", response_model=UploadOut)
async def upload_zip(
    file: UploadFile = File(...),
    auth: AuthUser = Depends(get_current_user),
) -> UploadOut:
    """进展/验收交付件：ZIP（可含 PR 说明、Issue、截图等）。"""
    name = file.filename or ""
    if not name.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="只能上传 zip 文件格式")
    stored = f"{uuid.uuid4().hex[:12]}_{_safe_name(name, force_ext='.zip')}"

    def _zip_head(head: bytes) -> str | None:
        if not (
            head.startswith(b"PK\x03\x04")
            or head.startswith(b"PK\x05\x06")
            or head.startswith(b"PK\x07\x08")
        ):
            return "文件不是有效 ZIP"
        return None

    out = await _stream_upload(
        file,
        auth_id=auth.id,
        stored_name=stored,
        max_bytes=MAX_ZIP_BYTES,
        oversize_detail="文件最大不超过 100M",
        validate_head=_zip_head,
    )
    return UploadOut(url=out.url, filename=name, size=out.size)


@router.get("/files/{user_part}/{filename}")
def get_uploaded_file(
    user_part: str,
    filename: str,
    access_token: str | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> FileResponse:
    if not re.fullmatch(r"u\d+", user_part):
        raise HTTPException(status_code=404, detail="not found")
    if "/" in filename or ".." in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="文件不存在")
    path = (UPLOAD_ROOT / user_part / filename).resolve()
    if UPLOAD_ROOT.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    lower = filename.lower()
    owner_id = int(user_part[1:])
    site_media_ext = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm")
    rel = f"/api/v1/uploads/files/{user_part}/{filename}"
    # 组委会站点图/视频、用户头像、社区 Logo/主页图：访客可直接打开；简历/zip 等仍要登录
    is_site_media = lower.endswith(site_media_ext) and _owner_is_committee(db, owner_id)
    is_avatar = lower.endswith(tuple(IMAGE_EXTS)) and _is_user_avatar(db, owner_id, rel)
    is_community_public = lower.endswith(tuple(IMAGE_EXTS)) and _is_community_public_image(
        db, rel
    )
    public_media = is_site_media or is_avatar or is_community_public
    if not public_media:
        viewer = _viewer(db, credentials, access_token)
        if viewer is None:
            raise HTTPException(status_code=401, detail="请先登录后再下载")
        if not _can_download(db, viewer, owner_id):
            raise HTTPException(status_code=403, detail="无权下载该文件")

    media = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    disposition = "inline"
    if lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm")):
        if lower.endswith((".jpg", ".jpeg")):
            media = "image/jpeg"
        elif lower.endswith(".png"):
            media = "image/png"
        elif lower.endswith(".webp"):
            media = "image/webp"
        elif lower.endswith(".gif"):
            media = "image/gif"
    else:
        if lower.endswith(".pdf"):
            media = "application/pdf"
        elif lower.endswith(".zip"):
            media = "application/zip"
        disposition = "attachment"
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "public, max-age=86400" if public_media else "private, no-store",
    }
    return FileResponse(
        path,
        media_type=media,
        filename=filename,
        content_disposition_type=disposition,
        headers=headers,
    )


def _viewer(
    db: Session,
    credentials: HTTPAuthorizationCredentials | None,
    access_token: str | None,
) -> AuthUser | None:
    token = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    elif access_token:
        token = access_token
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        return None
    user = db.get(User, user_id)
    if user is None:
        return None
    # 与 get_current_user 一致：改密吊销 + 停用账号不能再下私有附件
    from intern_platform.dependencies.auth import password_token_stamp, user_is_disabled

    token_pv = payload.get("pv")
    if token_pv is None or token_pv != password_token_stamp(user.password_hash):
        return None
    if user_is_disabled(db, user.id):
        return None
    return AuthUser(user=user, roles=load_user_roles(db, user.id))


def _owner_is_committee(db: Session, owner_id: int) -> bool:
    from sqlalchemy import select

    from intern_platform.models.role import Role, UserRole

    role = db.scalar(select(Role).where(Role.code == "committee"))
    if role is None:
        return False
    return (
        db.scalar(
            select(UserRole.id).where(
                UserRole.user_id == owner_id,
                UserRole.role_id == role.id,
            ).limit(1)
        )
        is not None
    )


def _is_user_avatar(db: Session, owner_id: int, rel: str) -> bool:
    user = db.get(User, owner_id)
    if user is None:
        return False
    current = (getattr(user, "avatar_url", None) or "").strip()
    return bool(current) and current == rel


def _is_community_public_image(db: Session, rel: str) -> bool:
    """社区对外展示的 Logo / 主页配图需匿名可读（项目列表、社区主页）。"""
    from sqlalchemy import or_, select

    from intern_platform.models.community import Community

    path = (rel or "").strip()
    if not path:
        return False
    # 兼容偶发带 query 的旧数据
    path = path.split("?", 1)[0]
    hit = db.scalar(
        select(Community.id)
        .where(
            or_(
                Community.logo_url == path,
                Community.logo_url == rel,
                Community.intro_body.contains(path),
            )
        )
        .limit(1)
    )
    return hit is not None


def _can_download(db: Session, viewer: AuthUser, owner_id: int) -> bool:
    """本人 / 组委会 / 名下课题导师 / 同社区管理员可下载。"""
    if viewer.id == owner_id:
        return True
    if viewer.has_role("committee"):
        return True

    from sqlalchemy import select

    from intern_platform.models.application import Application
    from intern_platform.models.project import Project

    if viewer.has_role("mentor"):
        linked = db.scalar(
            select(Application.id)
            .join(Project, Project.id == Application.project_id)
            .where(
                Project.mentor_id == viewer.id,
                Application.student_id == owner_id,
            )
            .limit(1)
        )
        if linked is not None:
            return True

    community_ids = viewer.community_ids_for("community_admin")
    if community_ids:
        linked = db.scalar(
            select(Application.id)
            .join(Project, Project.id == Application.project_id)
            .where(
                Project.community_id.in_(community_ids),
                Application.student_id == owner_id,
            )
            .limit(1)
        )
        if linked is not None:
            return True
        # 同社区其他管理员上传的材料等
        from intern_platform.models.role import Role, UserRole

        admin_role = db.scalar(select(Role).where(Role.code == "community_admin"))
        if admin_role is not None:
            peer = db.scalar(
                select(UserRole.id).where(
                    UserRole.user_id == owner_id,
                    UserRole.role_id == admin_role.id,
                    UserRole.community_id.in_(community_ids),
                ).limit(1)
            )
            if peer is not None:
                return True
    return False
