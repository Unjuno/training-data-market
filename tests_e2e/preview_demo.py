"""Local demo screenshot generator; screenshots contain synthetic data."""
import asyncio
from pathlib import Path
import re
from playwright.async_api import async_playwright

root=Path(__file__).resolve().parents[1]


def remove_modules(js):
  js=re.sub(r'(?m)^import .*?;\s*$', '', js)
  js=re.sub(r'(?m)^export\s+(?=(const|function|class)\b)', '', js)
  return js

async def main():
  markup=(root/'index.html').read_text()
  markup=re.sub(r'<link rel="stylesheet" href="[^"]+">', '', markup)
  markup=re.sub(r'<script type="module" src="[^"]+"></script>', '', markup)
  markup=markup.replace('</head>', '<style>'+(root/'styles.css').read_text()+(root/'live.css').read_text()+'</style></head>')
  js='\n'.join(remove_modules((root/file).read_text()) for file in ['src/demo-data.js','src/selection.js','src/draft.js','src/arena-view.js','app.js'])
  async with async_playwright() as p:
    browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    for width in (390,820,1440):
      page=await browser.new_page(viewport={'width':width,'height':900},device_scale_factor=1)
      errors=[];page.on('pageerror',lambda exc:errors.append(str(exc)))
      await page.set_content(markup,wait_until='domcontentloaded')
      await page.add_script_tag(content=js)
      await page.locator('.sample-card').first.wait_for()
      await page.screenshot(path=f'/mnt/data/training-data-market-ux-v0.7-{width}.png',full_page=True)
      overflow=await page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
      print(width,'cards',await page.locator('.sample-card').count(),'overflow',overflow,'js_errors',errors)
      assert not overflow and not errors
      await page.close()
    await browser.close()
if __name__=='__main__': asyncio.run(main())
