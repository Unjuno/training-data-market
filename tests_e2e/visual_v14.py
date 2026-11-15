"""Browser regressions for the game-first visual hierarchy and first-action affordance."""
import asyncio
from playwright.async_api import async_playwright
from tests_e2e.ux_flow import page_setup

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        for width in (390,820,1440):
            page=await page_setup(browser,width)
            overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert not overflow,f'{width}: horizontal overflow'
            explore_top=await page.locator('#explore').evaluate('(e)=>e.getBoundingClientRect().top+scrollY')
            assert explore_top < (1550 if width==390 else 1300),f'{width}: explorer pushed too far: {explore_top}'
            if width==390:
                metrics=await page.evaluate('''() => ({cols:getComputedStyle(document.querySelector('.summary-metrics')).gridTemplateColumns.split(' ').length,values:[...document.querySelectorAll('.summary-metric strong')].map(e=>({value:e.textContent,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}))})''')
                assert metrics['cols']==2,metrics
                assert all(x['height']<40 for x in metrics['values']),metrics
                assert await page.locator('.mobile-vote-link').get_attribute('href')=='#explore'
                await page.locator('.sample-card .select-button').first.click()
                await page.wait_for_function('document.getElementById("my-count").textContent.trim()==="1 / 10"')
                assert await page.locator('.mobile-vote-link').get_attribute('href')=='#vote-panel'
            print(f'{width}: explorer top {explore_top:.0f}px; overflow {overflow}')
            await page.close()
        await browser.close()

if __name__=='__main__':
    asyncio.run(main())
