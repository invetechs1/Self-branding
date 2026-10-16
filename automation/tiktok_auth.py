#!/usr/bin/env python3
"""ربط حساب تيك توك — يحصل على رموز الوصول ويحفظها في config.yml.

قبل التشغيل، جهّز تطبيقاً على developers.tiktok.com:
  1. أنشئ تطبيقاً واطلب منتج "Content Posting API".
  2. فعّل الصلاحيات: user.info.basic + video.upload (وأضف video.publish إن أردت النشر المباشر).
  3. سجّل رابط التحويل Redirect URI نفسه الموجود في config.yml.
  4. انسخ Client key و Client secret إلى config.yml.

ثم:
    python automation/tiktok_auth.py            # فتح الرابط ولصق رابط العودة
    python automation/tiktok_auth.py --server   # التقاط الرمز تلقائياً عبر خادم محلي
    python automation/tiktok_auth.py --check    # التحقق من الحساب المربوط حالياً
"""

from __future__ import annotations

import argparse
import secrets
import sys
import threading
import urllib.parse as up
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiktok as tk  # noqa: E402

CONFIG = tk.CONFIG


def load_cfg() -> dict:
    if not CONFIG.exists():
        sys.exit("لا يوجد automation/config.yml — انسخ config.example.yml وعبّئ مفاتيح تيك توك.")
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    t = cfg.get("tiktok") or {}
    missing = [k for k in ("client_key", "client_secret", "redirect_uri") if not t.get(k)]
    if missing:
        sys.exit("ينقص في config.yml → tiktok: " + "، ".join(missing)
                 + "\nاحصل عليها من developers.tiktok.com ← تطبيقك ← Manage apps")
    return cfg


def authorize_url(cfg: dict, state: str) -> str:
    t = cfg["tiktok"]
    scope = tk.SCOPES.get((t.get("mode") or "inbox").lower(), tk.SCOPES["inbox"])
    return tk.AUTH_URL + "?" + up.urlencode({
        "client_key": t["client_key"], "scope": scope, "response_type": "code",
        "redirect_uri": t["redirect_uri"], "state": state})


def code_from_input(raw: str) -> str:
    """يقبل الرمز وحده أو رابط العودة كاملاً."""
    raw = raw.strip()
    if raw.startswith("http"):
        qs = up.parse_qs(up.urlparse(raw).query)
        if "error" in qs:
            sys.exit(f"تيك توك رفض التفويض: {qs['error'][0]} — {qs.get('error_description', [''])[0]}")
        if "code" not in qs:
            sys.exit("الرابط لا يحوي code — انسخ رابط العودة كاملاً من شريط المتصفح.")
        return up.unquote(qs["code"][0])
    return up.unquote(raw)


def catch_with_server(cfg: dict, state: str) -> str:
    """يشغّل خادماً محلياً يلتقط رمز التفويض تلقائياً."""
    parsed = up.urlparse(cfg["tiktok"]["redirect_uri"])
    if parsed.hostname not in ("127.0.0.1", "localhost"):
        sys.exit("--server يعمل فقط مع redirect_uri محلي (مثل http://127.0.0.1:8721/callback)")
    got: dict = {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            qs = up.parse_qs(up.urlparse(self.path).query)
            got.update({k: v[0] for k, v in qs.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            ok = "code" in got
            self.wfile.write(("<html dir='rtl'><body style='font-family:sans-serif;padding:40px'>"
                              + ("<h2>تم الربط ✓</h2><p>أغلق هذه الصفحة وعُد إلى الطرفية.</p>"
                                 if ok else f"<h2>فشل التفويض</h2><p>{got}</p>")
                              + "</body></html>").encode("utf-8"))

    srv = HTTPServer((parsed.hostname, parsed.port or 80), H)
    worker = threading.Thread(target=srv.handle_request, daemon=True)
    worker.start()
    print(f"\nافتح هذا الرابط في المتصفح وسجّل الدخول بحسابك:\n\n{authorize_url(cfg, state)}\n")
    print("بانتظار عودة تيك توك (مهلة ٥ دقائق) ...")
    worker.join(timeout=300)
    srv.server_close()
    if not got:
        sys.exit("انتهت المهلة بلا رد — أعد المحاولة، أو استخدم الوضع اليدوي بلا --server.")
    if "error" in got:
        sys.exit(f"تيك توك رفض التفويض: {got.get('error')} — {got.get('error_description', '')}")
    if got.get("state") != state:
        sys.exit("قيمة state غير مطابقة — أوقفت العملية احتياطاً.")
    return up.unquote(got["code"])


def connect(args) -> None:
    cfg = load_cfg()
    state = secrets.token_urlsafe(16)
    if args.server:
        code = catch_with_server(cfg, state)
    else:
        print(f"\n١) افتح هذا الرابط وسجّل الدخول بحساب تيك توك الذي تريد ربطه:\n\n{authorize_url(cfg, state)}\n")
        print("٢) بعد الموافقة سيحوّلك تيك توك إلى رابط العودة.")
        code = code_from_input(input("٣) الصق رابط العودة كاملاً هنا ثم Enter:\n> "))

    body = tk.exchange_code(cfg, code)
    t = cfg["tiktok"]
    t["access_token"] = body["access_token"]
    t["refresh_token"] = body.get("refresh_token", "")
    if not tk.save_tokens(t):
        sys.exit("تعذّر الحفظ في config.yml — تحقق من صلاحيات الملف.")
    print(f"\n✓ حُفظت الرموز في {tk.CONFIG}")
    print(f"  الصلاحيات الممنوحة: {body.get('scope', '—')}")
    show_account(cfg)


def show_account(cfg: dict) -> None:
    try:
        info = tk.creator_info(cfg)
    except tk.TikTokError as e:
        print(f"\nتحذير: تعذّر قراءة بيانات الحساب — {e}")
        print("إن كان السبب الصلاحيات، فالنشر عبر وضع inbox قد يعمل رغم ذلك.")
        return
    print(f"\nالحساب المربوط: @{info.get('creator_username', '—')} ({info.get('creator_nickname', '')})")
    print(f"  أقصى مدة فيديو: {info.get('max_video_post_duration_sec', '—')} ثانية")
    print(f"  خيارات الخصوصية المتاحة: {', '.join(info.get('privacy_level_options', []) or ['—'])}")
    mode = (cfg['tiktok'].get('mode') or 'inbox').lower()
    print(f"\nالوضع الحالي: {mode}"
          + ("  (الفيديو يصل إلى مسودات التطبيق وتنشره بنفسك)" if mode == "inbox"
             else "  (نشر مباشر — يتطلب تدقيق تيك توك للتطبيق)"))


def main() -> None:
    ap = argparse.ArgumentParser(description="ربط حساب تيك توك بالنظام")
    ap.add_argument("--server", action="store_true", help="التقاط الرمز تلقائياً عبر خادم محلي")
    ap.add_argument("--check", action="store_true", help="عرض الحساب المربوط حالياً")
    ap.add_argument("--refresh", action="store_true", help="تجديد رمز الوصول يدوياً")
    args = ap.parse_args()

    if args.check:
        show_account(load_cfg())
    elif args.refresh:
        cfg = load_cfg()
        tk.refresh_access_token(cfg)
        print("✓ جُدِّد رمز الوصول وحُفظ.")
    else:
        connect(args)


if __name__ == "__main__":
    main()
