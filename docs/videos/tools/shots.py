#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يلتقط صوراً لمشاهد محددة — لمراجعة التصميم قبل تسجيل ثلاث دقائق كاملة.

    python docs/videos/tools/shots.py improvements.html 0 3 7

يثبّت المشهد المطلوب بأنماط مباشرة (تتجاوز حركة الصفحة) فتخرج اللقطة نظيفة.
"""

import asyncio
import os
import sys
from pathlib import Path

CHROME = os.environ.get("CHROME_BIN")

FORCE = """(i) => {
  document.querySelectorAll('.scene').forEach(s => {
    s.style.opacity = '0'; s.style.transform = 'none'; s.style.zIndex = '0';
  });
  const sc = document.getElementById('s' + i);
  if (!sc) return false;
  sc.style.opacity = '1'; sc.style.zIndex = '10';
  sc.querySelectorAll('.rise').forEach(e => { e.style.opacity = '1'; e.style.transform = 'none'; });
  sc.querySelectorAll('.wbar > i').forEach(x => x.style.width = x.dataset.w + 'px');
  return true;
}"""


async def main() -> None:
    from playwright.async_api import async_playwright
    page_path = Path(sys.argv[1])
    wanted = [int(x) for x in sys.argv[2:]] or [0]
    launch = {"args": ["--no-sandbox", "--disable-gpu"]}
    if CHROME:
        launch["executable_path"] = CHROME

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**launch)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        await page.goto(page_path.resolve().as_uri())
        for i in wanted:
            found = await page.evaluate(FORCE, i)
            if not found:
                print(f"  لا يوجد مشهد رقم {i}")
                continue
            await page.wait_for_timeout(500)
            out = page_path.with_name(f"{page_path.stem}-{i}.png")
            await page.screenshot(path=str(out))
            print(f"  {out}")
        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("الاستخدام: shots.py <page.html> [أرقام المشاهد]")
    asyncio.run(main())
