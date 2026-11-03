#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يسجّل صفحة مشاهد ويحوّلها إلى mp4.

    python docs/videos/tools/record.py improvements.html 06-seven-improvements.mp4

المتطلبات:
    pip install playwright imageio-ffmpeg
    playwright install chromium          # أو حدّد متصفحك بمتغير CHROME_BIN

الصفحة تُعلم انتهاءها بـ window.__done، فالتسجيل يتوقف تلقائياً عند آخر مشهد.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

CHROME = os.environ.get("CHROME_BIN")      # اتركه فارغاً ليستخدم متصفح playwright


async def record(page_path: Path, out_mp4: Path) -> None:
    import imageio_ffmpeg
    from playwright.async_api import async_playwright

    vdir = out_mp4.parent / "_raw"
    vdir.mkdir(parents=True, exist_ok=True)
    launch = {"args": ["--no-sandbox", "--disable-gpu"]}
    if CHROME:
        launch["executable_path"] = CHROME

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**launch)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 720},
                                        record_video_dir=str(vdir),
                                        record_video_size={"width": 1280, "height": 720})
        page = await ctx.new_page()
        await page.goto(page_path.resolve().as_uri())
        print("التسجيل جارٍ — ينتهي تلقائياً عند آخر مشهد ...")
        await page.wait_for_function("window.__done === true", timeout=900_000)
        video = page.video
        await ctx.close()
        await browser.close()
        webm = Path(await video.path())

    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(webm),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "25",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-r", "24",
                    str(out_mp4)], check=True, capture_output=True)
    webm.unlink(missing_ok=True)
    try:
        vdir.rmdir()
    except OSError:
        pass
    print(f"{out_mp4} — {out_mp4.stat().st_size / 1024 / 1024:.1f} ميغابايت")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("الاستخدام: record.py <page.html> <out.mp4>")
    asyncio.run(record(Path(sys.argv[1]), Path(sys.argv[2])))
