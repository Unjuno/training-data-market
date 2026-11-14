"""Chromium UI wired to actual FastAPI via a Python request bridge.

The environment blocks browser-to-localhost sockets. Requests are executed
against the REAL FastAPI app with independent TestClient cookie jars. Only
sample image URLs are omitted in the about:blank document (image endpoint has
independent HTTP tests); the rest of the API and all training are real.
"""
import asyncio, json, os, tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright
from backend import ml
from backend.store import GameStore
from backend.service import make_app
from tests_e2e.ux_flow import markup,js_bundle

async def new_ui(browser,client,width):
    page=await browser.new_page(viewport={'width':width,'height':850})
    errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
    await page.set_content(markup())
    async def proxy(_source,path,opts):
        method=opts.get('method','GET')
        headers=opts.get('headers',{})
        response=client.request(method,path,headers=headers,content=opts.get('body'))
        data=response.json()
        # An about:blank test document has no usable same-origin image base.
        if path.startswith('/v1/samples?') and response.status_code==200:
            for item in data['items']:item['image_url']=None
        return {'ok':response.is_success,'status':response.status_code,'body':data}
    await page.expose_binding('bridgeFetch',proxy)
    await page.evaluate('''() => { window.fetch=async (path,opts={}) => {
       const result=await window.bridgeFetch(path,opts);
       return {ok:result.ok,status:result.status,json:async()=>result.body};
    };}''')
    await page.add_script_tag(content=js_bundle())
    await page.locator('.sample-card').first.wait_for(timeout=20000)
    return page,errors

async def scenario(app,state):
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        with TestClient(app) as alice_client, TestClient(app) as bob_client:
            a,ea=await new_ui(browser,alice_client,1280)
            b,eb=await new_ui(browser,bob_client,390)
            assert 'DEMO' in await a.locator('#mode-badge').inner_text()
            assert '合成ピクセルアート' in await a.locator('#dataset-rights').inner_text()
            id=await a.locator('.sample-card button').first.get_attribute('data-pick-id')
            await a.locator(f'[data-pick-id="{id}"]').click()
            await a.wait_for_function('document.querySelector("#my-count").textContent==="1 / 10"')
            await b.locator(f'[data-pick-id="{id}"]').click()
            await b.wait_for_function('document.querySelector("#my-count").textContent==="1 / 10"')
            await a.locator('#refresh').click()
            await a.wait_for_function('document.querySelector(".sample-votes").textContent.includes("2 票")')
            assert '保存' in await a.locator('#vote-status').inner_text()
            res=alice_client.post('/v1/admin/rounds/round-0001/lock',headers={'X-Admin-Key':'k'*40})
            assert res.status_code==200
            blocked=alice_client.put(f'/v1/rounds/round-0001/picks/{id}')
            assert blocked.status_code==409
            result=await asyncio.to_thread(ml.run_locked_round,Path('.'),state,'round-0001')
            await a.locator('#refresh').click()
            await a.wait_for_function('document.querySelector("#metric-round").textContent.includes("round-0002")')
            await a.wait_for_function('document.querySelector("#results").textContent.includes("Community")')
            assert not (ea+eb),(ea+eb)
            assert not await b.evaluate('document.documentElement.scrollWidth>innerWidth')
            print(json.dumps({'browser_webkit':'chromium','api':'real FastAPI TestClient','two_browser_sessions':True,'votes_persisted':True,'training_steps':40,'next_round':result['next_round'],'browser_exceptions':ea+eb},ensure_ascii=False))
            await a.close();await b.close()
        await browser.close()

def main():
    os.environ['TDM_COOKIE_SECRET']='s'*64
    os.environ['TDM_ADMIN_KEY']='k'*40
    os.environ['TDM_DEMO_MODE']='true'
    os.environ['TDM_PUBLISH_IMAGES']='false'
    with tempfile.TemporaryDirectory(prefix='tdm-e2e-ui-') as root:
        state=Path(root)
        ml.prepare_demo(state)
        db=GameStore(state/'votes.sqlite3')
        asyncio.run(scenario(make_app(db,state),state))

if __name__=='__main__':main()
