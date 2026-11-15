"""Optional Chromium UX regression checks (local mock API, not deployed Sites)."""
import asyncio
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def markup():
    html=(ROOT/'live.html').read_text()
    html=re.sub(r'<link rel="stylesheet" href="[^"]+">','',html)
    html=re.sub(r'<script type="module" src="[^"]+"></script>','',html)
    css=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'live.css').read_text()+'\n'+(ROOT/'game.css').read_text()
    return html.replace('</head>','<style>'+css+'</style></head>')


def js_bundle():
    parts=[]
    for name in ['src/arena-view.js','src/deadline.js','src/round-flow.js','src/game-view.js','live.js']:
        content=(ROOT/name).read_text()
        content=re.sub(r'(?m)^import .*?;\s*$','',content)
        content=re.sub(r'(?m)^export\s+(?=(const|function|class)\b)','',content)
        parts.append(content)
    return '\n'.join(parts)

MOCK='''() => {
 window.__mock={picks:[],failVote:false,failSamples:false,status:'OPEN',requests:[],
  samples:Array.from({length:50},(_,i)=>({id:101+i,label:i%10,prediction:{predicted:i%2?i%10:(i+1)%10,loss:1.3-i/100},votes:0,image_url:null}))};
 const res=(status,data)=>({ok:status<400,status,json:async()=>data});
 window.fetch=async(input,opts={})=>{
  const url=String(input),method=opts.method||'GET',s=window.__mock;
  s.requests.push(method+' '+url);
  if(url==='/v1/rounds/current')return res(200,{mode:'LIVE',server_time:Date.now()/1000,round:{id:'r1',status:s.status,targets:[3,5],closes_at:s.deadlineSeconds||Date.now()/1000+3600},vote_summary:{vote_count:24,voter_count:8,forecast_count:3,frozen:s.status!=='OPEN'},metrics:{public:{overall_loss:0.8,accuracy:0.61}}});
  if(url.endsWith('/picks/me'))return res(200,{ids:[...s.picks],note:''});
  if(url.startsWith('/v1/samples?')){
   if(s.failSamples)return res(503,{error:'モデルの予測結果を準備中です'});
   const q=new URLSearchParams(url.split('?')[1]);const needle=q.get('query')||'';
   const all=s.samples.filter(x=>!needle||String(x.id).includes(needle)||(needle==='cat'&&x.label===3));
   const page=Number(q.get('page')),limit=Number(q.get('limit'));
   return res(200,{items:all.slice((page-1)*limit,page*limit),total:all.length,page,limit,image_rights_approved:false,predictions_stale:false});
  }
  if(url==='/v1/rounds/history')return res(200,{items:[]});
  if(url.includes('/picks/')&&method==='PUT'){
   if(s.failVote)return res(503,{error:'サーバーに保存できません'});
   const id=Number(url.split('/').pop());if(!s.picks.includes(id))s.picks.push(id);return res(200,{status:'created'});
  }
  if(url.includes('/picks/')&&method==='DELETE'){
   const id=Number(url.split('/').pop());s.picks=s.picks.filter(x=>x!==id);return res(200,{deleted:true});
  }
  if(url.endsWith('/note')&&method==='PUT')return res(200,{status:'saved'});
  return res(404,{error:'unrecognized '+url});
 }
}'''

async def page_setup(browser,width):
    page=await browser.new_page(viewport={'width':width,'height':900})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    await page.set_content(markup(),wait_until='domcontentloaded')
    await page.evaluate(MOCK)
    await page.add_script_tag(content=js_bundle())
    await page.locator('.sample-card').first.wait_for()
    assert not errors,errors
    return page

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await page_setup(browser,1440)
        # The ID field must reject scientific notation, not silently vote for #100.
        await page.locator('#sample-id').fill('1e2')
        await page.locator('#id-form-live').evaluate(
            "form => form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))")
        await page.wait_for_timeout(250)
        requests=await page.evaluate('window.__mock.requests')
        assert not any(req.startswith('PUT ') and req.endswith('/picks/100') for req in requests), \
            'scientific notation must not be accepted as a different image ID'
        assert '画像ID' in await page.locator('#vote-status').inner_text()
        # Debounced search updates without requiring an explicit submission.
        await page.locator('#query').fill('103')
        await page.wait_for_timeout(450)
        assert await page.locator('.sample-card').count()==1,'search was not auto-applied'
        await page.locator('#query').fill('')
        await page.wait_for_timeout(450)
        # Selected image button retains keyboard focus after a successful remote vote.
        await page.locator('[data-pick-id="101"]').focus()
        await page.keyboard.press('Enter')
        await page.wait_for_function("document.querySelector('#my-count').textContent==='1 / 10'")
        assert await page.evaluate("document.activeElement?.dataset?.pickId")=='101','focus lost on re-render'
        assert 'サーバーに保存' in await page.locator('#vote-status').inner_text()
        # Remote picks refresh while maintaining typed, unsaved note.
        await page.locator('#reason-live').fill('この画像は特徴が違うため学習に効くと考える')
        await page.evaluate('window.__mock.picks=[101,102]')
        await page.locator('#refresh').click()
        await page.wait_for_function("document.querySelector('#my-count').textContent==='2 / 10'")
        assert await page.locator('#reason-live').input_value()=='この画像は特徴が違うため学習に効くと考える'
        # Failed vote does not clear typed ID; provides actionable message.
        await page.evaluate('window.__mock.failVote=true')
        await page.locator('#sample-id').fill('103')
        await page.locator('#id-form-live button').click()
        assert await page.locator('#sample-id').input_value()=='103','input destroyed on failure'
        assert '再試行' in await page.locator('#vote-status').inner_text()
        # Fetch failure has an explicit retry and is not portrayed as empty search results.
        await page.evaluate('window.__mock.failSamples=true')
        await page.locator('#filters button[type="submit"]').click()
        await page.wait_for_function("document.querySelector('#empty-state').hidden===false")
        assert '取得できません' in await page.locator('#empty-state h3').inner_text()
        assert await page.locator('#empty-action').is_visible()
        await page.evaluate('window.__mock.failSamples=false')
        await page.locator('#empty-action').click()
        await page.locator('.sample-card').first.wait_for()
        assert await page.locator('#empty-state').is_hidden(),'retry did not recover'
        await page.close()
        # On mobile, a page has at most 12 cards and the vote phase is explicit.
        mobile=await page_setup(browser,390)
        assert await mobile.locator('.sample-card').count()<=12,'mobile page too long'
        assert '推薦受付中' in await mobile.locator('#round-phase').inner_text()
        assert await mobile.locator('#next-page-bottom').is_visible(),'no bottom pagination after scrolling data cards'
        await mobile.locator('#next-page-bottom').click()
        await mobile.wait_for_function("document.querySelector('#page-caption').textContent.includes('13–24')")
        assert await mobile.locator('#page-caption').get_attribute('aria-live')=='polite','result count not announced to assistive technology'
        overflow=await mobile.evaluate('document.documentElement.scrollWidth>window.innerWidth')
        assert not overflow,'horizontal overflow'
        # The shared time-gated process has four explicit phases and real counts.
        assert '投票受付中' in await mobile.locator('#batch-stage').inner_text()
        assert await mobile.locator('#batch-voter-count').inner_text()=='8'
        assert await mobile.locator('#batch-pick-count').inner_text()=='24'
        assert await mobile.locator('#batch-forecast-count').inner_text()=='3'
        await mobile.evaluate("window.__mock.status='TRAINING'")
        await mobile.locator('#refresh').click()
        await mobile.wait_for_function("document.querySelector('#batch-stage').textContent==='バッチ学習中'")
        assert await mobile.locator('#batch-rail').get_attribute('data-stage')=='training'
        assert not await mobile.locator('#sample-id').is_enabled()
        # The deadline UI must disable votes without waiting for the worker.
        await mobile.evaluate("window.__mock.status='OPEN'")
        await mobile.evaluate('window.__mock.deadlineSeconds=Date.now()/1000-1')
        await mobile.locator('#refresh').click()
        await mobile.wait_for_function('document.querySelector("#sample-id").disabled===true')
        assert '締切' in await mobile.locator('#round-countdown').inner_text()
        # Sticky shortcut must not cover the result recap on mobile.
        await mobile.locator('#how-it-works').scroll_into_view_if_needed()
        await mobile.wait_for_timeout(350)
        assert 'is-visible' not in (await mobile.locator('.mobile-vote-link').get_attribute('class'))
        await mobile.close();await browser.close()
    print('PASS: UX browser workflow (search, vote, focus, refresh, errors, mobile)')

if __name__=='__main__': asyncio.run(main())
