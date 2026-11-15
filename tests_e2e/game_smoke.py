"""Chromium 144 browser UX + real HTTP bridge smoke for sandboxed environments.

Native browser navigation to localhost is policy-blocked in this container, so
we load the same HTML/CSS/JS using set_content and proxy requests to the local
FastAPI through Python. This is *not* a Google Chrome-native or Sites test.
"""
from pathlib import Path
import argparse, http.cookiejar, json, re, threading, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
from backend.store import GameStore
from backend.ml import run_locked_round

ROOT=Path(__file__).resolve().parents[1]

def bridge(api_root):
    jar=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    lock=threading.Lock()
    def invoke(url,method='GET',body=None):
        req=urllib.request.Request(api_root+url,data=body.encode() if body is not None else None,
                                   method=method,headers={'Content-Type':'application/json'})
        with lock:
            try:
                with opener.open(req,timeout=50) as reply:
                    return {'status':reply.status,'data':json.loads(reply.read())}
            except urllib.error.HTTPError as error:
                return {'status':error.code,'data':json.loads(error.read())}
    return invoke

def serve_asset(route,api_root):
    u=route.request.url.replace('https://tdm.test',api_root,1)
    try:
        with urllib.request.urlopen(u,timeout=45) as answer:
            route.fulfill(status=answer.status,body=answer.read(),headers={'content-type':answer.headers.get('Content-Type','application/octet-stream')})
    except urllib.error.HTTPError as error:
        route.fulfill(status=error.code,body=error.read())


def test_flow(port:int,state:Path,out:Path):
    api_root=f'http://127.0.0.1:{port}'
    content=(ROOT/'live.html').read_text(encoding='utf8').replace('<script type="module" src="live.js"></script>','')
    content=content.replace('</head>','<base href="https://tdm.test/"></head>')
    sources=[]
    for f in ['src/arena-view.js','src/deadline.js','src/round-flow.js','src/game-view.js','live.js']:
        src=(ROOT/f).read_text(encoding='utf-8')
        src=re.sub(r'(?m)^import .*?;\s*$', '', src)
        src=re.sub(r'(?m)^export\s+', '', src)
        sources.append(src)
    script='\n'.join(sources).replace('window.location.origin',"'https://tdm.test'")
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':900},device_scale_factor=1)
        page.route('https://tdm.test/**',lambda r:serve_asset(r,api_root))
        page.expose_function('__bridgeRequest',bridge(api_root))
        page.set_content(content,wait_until='domcontentloaded')
        for css in ['styles.css','live.css','game.css','experience.css']:
            page.add_style_tag(content=(ROOT/css).read_text(encoding='utf8'))
        page.evaluate('''() => {window.fetch=async(url,opts={})=>{
            const r=await window.__bridgeRequest(url,opts.method||'GET',opts.body||null);
            return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.data};
        };}''')
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.add_script_tag(content=script)
        page.wait_for_function('document.querySelectorAll(".sample-card").length > 0',timeout=60000)
        current=json.load(urllib.request.urlopen(api_root+'/v1/rounds/current'))['round']['id']
        page.locator('.sample-card .select-button').first.click()
        page.wait_for_function('document.getElementById("my-count").textContent.trim().startsWith("1 / 10")')
        page.locator('#forecast-range').fill('75')
        page.locator('#forecast-save').click()
        page.wait_for_function('document.getElementById("forecast-status").textContent.includes("保存しました")',timeout=20000)
        assert page.locator('#progress-forecast').get_attribute('class').find('is-done')>=0
        (out/'forecast.png').parent.mkdir(parents=True,exist_ok=True)
        page.locator('#prediction-section').screenshot(path=str(out/'forecast.png'))
        print('LOCK',current,flush=True)
        store=GameStore(state/'votes.sqlite3');store.lock_round(current)
        print('RUN TRAINING',flush=True)
        output=run_locked_round(Path('.'),state,current)
        print('TRAINING FINISHED',flush=True)
        print('REFRESH CLICK',flush=True)
        page.locator('#refresh').click()
        print('AFTER REFRESH CLICK',flush=True)
        page.wait_for_function('document.getElementById("forecast-last-result").textContent.includes("pt")',timeout=30000)
        print('SCORE VISIBLE',page.locator('#forecast-last-result').inner_text(),flush=True)
        assert current in page.locator('#forecast-last-result').inner_text()
        result_text=page.locator('#results').inner_text()
        assert 'Community' in result_text and 'Random' in result_text
        assert '共有AIへの反映' in result_text
        assert page.locator('#forecast-score-total').inner_text()!='0 pt'
        page.locator('#results-section').screenshot(path=str(out/'results.png'))
        assert errors==[],errors
        print('DESKTOP OK',current,output['promotion'],page.locator('#forecast-last-result').inner_text())
        page.close()
        mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
        mobile.route('https://tdm.test/**',lambda r:serve_asset(r,api_root))
        mobile.expose_function('__bridgeRequest',bridge(api_root))
        mobile.set_content(content,wait_until='domcontentloaded')
        for css in ['styles.css','live.css','game.css','experience.css']:
            mobile.add_style_tag(content=(ROOT/css).read_text(encoding='utf8'))
        mobile.evaluate('''() => {window.fetch=async(url,opts={})=>{
            const r=await window.__bridgeRequest(url,opts.method||'GET',opts.body||null);
            return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.data};
        };}''')
        mobile.add_script_tag(content=script)
        mobile.wait_for_function('document.querySelectorAll(".sample-card").length > 0',timeout=60000)
        assert not mobile.evaluate('document.documentElement.scrollWidth > innerWidth')
        mobile.locator('#strategy-a').click()
        mobile.wait_for_timeout(650)
        assert mobile.locator('#label-filter').input_value() != ''
        mobile.locator('#prediction-section').screenshot(path=str(out/'mobile-forecast.png'))
        print('MOBILE OK',mobile.locator('.sample-card').count())
        browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--state',type=Path,default=ROOT/'demo-state')
    parser.add_argument('--out',type=Path,default=Path('/mnt/data/tdm-v11-proof'))
    args=parser.parse_args();test_flow(args.port,args.state,args.out)
