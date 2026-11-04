#!/usr/bin/env python3
"""تكامل تيك توك — Content Posting API v2.

تيك توك لا ينشر نصاً: ينشر فيديو. لذلك يحتاج كل صف تيك توك في الطابور
ملف فيديو في عمود media_path، والسكربت في content يبقى للتصوير.

وضعان (mode في config.yml):
  inbox   — يرفع الفيديو إلى مسودات تطبيقك فتراجعه وتنشره بنفسك.
            يحتاج صلاحية video.upload فقط، ولا يحتاج تدقيق التطبيق. الافتراضي.
  direct  — نشر مباشر. يحتاج صلاحية video.publish وتدقيق تيك توك للتطبيق،
            وقبل التدقيق يُسمح بالخصوصية SELF_ONLY فقط.

المصادقة: python automation/tiktok_auth.py
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "automation" / "config.yml"
DEFAULT_API = "https://open.tiktokapis.com"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
SCOPES = {"inbox": "user.info.basic,video.upload", "direct": "user.info.basic,video.publish"}

# حدود تيك توك للرفع المجزّأ
MIN_CHUNK = 5 * 1024 * 1024
MAX_CHUNK = 64 * 1024 * 1024
TIMEOUT = 120


class TikTokError(Exception):
    """فشل نداء تيك توك — الرسالة تحمل سبب المنصة كما ورد."""


def api_base(cfg: dict) -> str:
    return (cfg.get("tiktok", {}).get("api_base") or DEFAULT_API).rstrip("/")


def _call(cfg: dict, path: str, payload: dict | None = None, *, form: bool = False,
          token: str | None = None) -> dict:
    """نداء POST إلى تيك توك مع تفسير غلاف error القياسي."""
    url = f"{api_base(cfg)}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        r = requests.post(url, data=payload or {}, headers=headers, timeout=TIMEOUT)
    else:
        headers["Content-Type"] = "application/json; charset=UTF-8"
        r = requests.post(url, json=payload or {}, headers=headers, timeout=TIMEOUT)

    try:
        body = r.json()
    except ValueError:
        raise TikTokError(f"رد غير متوقع من تيك توك ({r.status_code}): {r.text[:160]}")

    err = body.get("error") or {}
    code = err.get("code") or body.get("error_description")
    if code and code not in ("ok", "", None):
        raise TikTokError(f"تيك توك رفض الطلب [{code}]: {err.get('message') or body.get('error_description', '')}")
    if r.status_code >= 400:
        raise TikTokError(f"تيك توك: HTTP {r.status_code} — {r.text[:160]}")
    return body


# ───────────────────────────── الرموز ─────────────────────────────

def exchange_code(cfg: dict, code: str) -> dict:
    """يحوّل رمز التفويض إلى access/refresh token."""
    t = cfg["tiktok"]
    body = _call(cfg, "/v2/oauth/token/", {
        "client_key": t["client_key"], "client_secret": t["client_secret"],
        "code": code, "grant_type": "authorization_code",
        "redirect_uri": t["redirect_uri"]}, form=True)
    return body


def refresh_access_token(cfg: dict, persist: bool = True) -> str:
    """يجدّد رمز الوصول (صالح ٢٤ ساعة) بواسطة refresh token (صالح سنة)."""
    t = cfg.get("tiktok", {})
    if not t.get("refresh_token"):
        raise TikTokError("لا يوجد refresh_token — شغّل python automation/tiktok_auth.py")
    body = _call(cfg, "/v2/oauth/token/", {
        "client_key": t["client_key"], "client_secret": t["client_secret"],
        "grant_type": "refresh_token", "refresh_token": t["refresh_token"]}, form=True)
    t["access_token"] = body["access_token"]
    if body.get("refresh_token"):
        t["refresh_token"] = body["refresh_token"]
    if persist:
        save_tokens(t)
    return t["access_token"]


def save_tokens(tiktok_cfg: dict) -> bool:
    """يحفظ الرموز المجدَّدة في config.yml (المستبعد من git). يفشل بصمت في CI."""
    if not CONFIG.exists():
        return False
    try:
        data = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        data.setdefault("tiktok", {}).update(
            {k: tiktok_cfg.get(k) for k in ("access_token", "refresh_token") if tiktok_cfg.get(k)})
        CONFIG.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return True
    except OSError:
        return False


def _token(cfg: dict) -> str:
    t = cfg.get("tiktok", {})
    return t.get("access_token") or refresh_access_token(cfg)


# ───────────────────────── معلومات الحساب ─────────────────────────

def creator_info(cfg: dict) -> dict:
    """بيانات الحساب وقيوده — تيك توك يوجب استدعاءها قبل النشر المباشر."""
    body = _call(cfg, "/v2/post/publish/creator_info/query/", {}, token=_token(cfg))
    return body.get("data", {})


# ───────────────────────────── النشر ─────────────────────────────

def _chunks(size: int) -> tuple[int, int]:
    """حجم الجزء وعددها وفق حدود تيك توك (٥–٦٤ ميغابايت)."""
    if size <= MAX_CHUNK:
        return size, 1
    # تيك توك: العدد = القسمة الصحيحة، والجزء الأخير يحمل الباقي مهما زاد
    return MAX_CHUNK, max(1, size // MAX_CHUNK)


def _init_payload(cfg: dict, size: int, caption: str, mode: str) -> tuple[str, dict]:
    chunk, count = _chunks(size)
    source = {"source": "FILE_UPLOAD", "video_size": size,
              "chunk_size": chunk, "total_chunk_count": count}
    if mode == "direct":
        t = cfg["tiktok"]
        return "/v2/post/publish/video/init/", {
            "post_info": {
                "title": caption[:2200],
                "privacy_level": t.get("privacy_level", "SELF_ONLY"),
                "disable_comment": bool(t.get("disable_comment", False)),
                "disable_duet": bool(t.get("disable_duet", False)),
                "disable_stitch": bool(t.get("disable_stitch", False)),
            },
            "source_info": source}
    return "/v2/post/publish/inbox/video/init/", {"source_info": source}


def _upload(upload_url: str, video: Path, chunk: int, count: int) -> None:
    size = video.stat().st_size
    with video.open("rb") as f:
        for i in range(count):
            start = i * chunk
            data = f.read(chunk if i < count - 1 else size - start)
            end = start + len(data) - 1
            r = requests.put(upload_url, data=data, timeout=TIMEOUT, headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(len(data)),
                "Content-Range": f"bytes {start}-{end}/{size}"})
            if r.status_code >= 300:
                raise TikTokError(f"فشل رفع الجزء {i + 1}/{count}: HTTP {r.status_code} {r.text[:120]}")


def publish(cfg: dict, video: Path, caption: str) -> dict:
    """يرفع الفيديو إلى تيك توك. يعيد publish_id والوضع المستخدم."""
    t = cfg.get("tiktok", {})
    mode = (t.get("mode") or "inbox").lower()
    if mode not in ("inbox", "direct"):
        raise TikTokError(f"وضع تيك توك غير معروف: {mode} (المتاح: inbox أو direct)")
    size = video.stat().st_size
    if size == 0:
        raise TikTokError(f"ملف الفيديو فارغ: {video.name}")

    path, payload = _init_payload(cfg, size, caption, mode)
    try:
        body = _call(cfg, path, payload, token=_token(cfg))
    except TikTokError as e:
        if "access_token" not in str(e) and "token" not in str(e).lower():
            raise
        body = _call(cfg, path, payload, token=refresh_access_token(cfg))

    data = body.get("data", {})
    upload_url, publish_id = data.get("upload_url"), data.get("publish_id")
    if not upload_url or not publish_id:
        raise TikTokError(f"رد تيك توك بلا رابط رفع: {body}")

    chunk, count = _chunks(size)
    _upload(upload_url, video, chunk, count)
    return {"publish_id": publish_id, "mode": mode, "size": size, "chunks": count}


def fetch_status(cfg: dict, publish_id: str) -> dict:
    body = _call(cfg, "/v2/post/publish/status/fetch/", {"publish_id": publish_id},
                 token=_token(cfg))
    return body.get("data", {})


# ───────────────────────── الكابشن من السكربت ─────────────────────────

CAPTION_MARK = re.compile(r"^\s*(?:الكابشن|الوصف|caption)\s*[:：]\s*(.+)$", re.I | re.M)


def extract_caption(text: str, limit: int = 150) -> str:
    """يستخرج الكابشن من نص السكربت: سطر «الكابشن:» وإلا الخطّاف (أول سطر مفيد)."""
    m = CAPTION_MARK.search(text or "")
    if m:
        return m.group(1).strip()[:limit]
    for line in (text or "").splitlines():
        clean = re.sub(r"^[\s\-•*\d.]+", "", line).strip()
        clean = re.sub(r"^\[[^\]]*\]\s*", "", clean)          # [خطّاف 3 ثوان]
        if len(clean) > 12:
            return clean[:limit]
    return ""


def caption_for(row: dict, limit: int = 150) -> str:
    return (row.get("caption") or "").strip()[:limit] or extract_caption(row.get("content", ""), limit)
