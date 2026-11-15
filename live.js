import {CLASS_NAMES,CLASS_KEYS,$,renderPicks,setSystemMessage,createSampleCard,updateQuest,setMetric,renderResults,setupMobileVoteLink} from './src/arena-view.js';
import {deadlineState} from './src/deadline.js';
import {batchPhase} from './src/round-flow.js';
import {questIntel,progressState,scoreSummary,forecastHint} from './src/game-view.js';
let current=null;let datasetName=null;let picks=new Set();let page=1,total=0;let busy=false;let requestVersion=0;
let searchDebounce=null;let noteDirty=false;let serverClockOffsetMs=0;let lastEditable=false;let autoRefreshing=false;
let forecastPct=null;let forecastDirty=false;let forecastBusy=false;let lastPublished=false;let voteSummary=null;
for(let i=0;i<CLASS_NAMES.length;i++){
  const option=document.createElement('option');option.value=String(i);option.textContent=CLASS_NAMES[i];$('label-filter').append(option);
}
function status(text,level='info'){$('vote-status').textContent=text;$('vote-status').dataset.level=level;}
function pageSize(){return window.innerWidth<=620?12:window.innerWidth<=850?24:48;}
function deadline(){return deadlineState(current,Date.now()+serverClockOffsetMs);} 
async function request(url,options={}){
  const response=await fetch(url,{credentials:'same-origin',cache:'no-store',...options});
  let data;try{data=await response.json();}catch{throw Error(`サーバーの応答形式に問題があります（HTTP ${response.status}）`);}
  if(!response.ok)throw Error(typeof(data.error||data.detail)==='string'?(data.error||data.detail):`HTTP ${response.status}`);
  return data;
}
function updateGameProgress(){
  const state=progressState(picks.size,forecastPct!==null,deadline().isOpen);
  $('player-next-step').textContent=state.next;
  for(const [id,done] of [['progress-watch',!!current],['progress-scout',state.selected],
                           ['progress-forecast',state.forecasted],['progress-reveal',lastPublished]]){
    const step=$(id);step.classList.toggle('is-done',done);
    step.classList.toggle('is-ready',!done && id===(state.selected?'progress-forecast':'progress-scout'));
  }
}
function syncForecastControls(){
  const enabled=deadline().isOpen;
  $('forecast-range').disabled=!enabled;
  $('forecast-save').disabled=!enabled||forecastBusy;
  if(!enabled&&current) $('forecast-status').textContent='締切済み：予測は変更できません。結果公開後に採点します。';
}
function renderForecastRecord(record){
  $('forecast-score-total').textContent=`${Number(record.total_points||0).toLocaleString('ja-JP')} pt`;
  $('forecast-score-summary').textContent=scoreSummary(record);
  const completed=(record.items||[]).find(item=>item.points!==null);
  $('forecast-last-result').textContent=completed?
    `${completed.round_id}：予測 ${completed.forecast_pct}% / ${completed.outcome==='community'?'Community勝利':'Random勝利'} → +${completed.points} pt`:
    '予測の採点結果はラウンド終了後に表示されます。';
}
async function refreshForecast(){
  if(!current){forecastPct=null;updateGameProgress();syncForecastControls();return;}
  try{
    const [state,record]=await Promise.all([
      request(`/v1/rounds/${encodeURIComponent(current.id)}/forecast/me`),
      request('/v1/game/me')]);
    forecastPct=state.probability_pct;
    if(!forecastDirty){
      $('forecast-range').value=String(forecastPct??60);
      $('forecast-pct').textContent=`${$('forecast-range').value}%`;
      $('forecast-hint').textContent=forecastHint(Number($('forecast-range').value));
      $('forecast-status').textContent=forecastPct!==null?
        `予測 ${forecastPct}% はサーバーに保存されています。締切まで更新可能です。`:
        'まだ予測を提出していません。';
    }
    $('forecast-save').firstChild.textContent=forecastPct!==null?'保存した予測を更新する ':'この予測を保存する ';
    renderForecastRecord(record);
  }catch(error){
    $('forecast-status').textContent='予測情報を取得できません：'+error.message+'。後でもう一度読み込んでください。';
    $('forecast-status').dataset.level='error';
  }
  syncForecastControls();updateGameProgress();
}
function applyStrategy(kind){
  if(!current)return;
  const [a,b]=current.targets;
  const labels={'a':a,'b':b};
  $('query').value='';$('label-filter').value=kind in labels?String(labels[kind]):'';
  $('wrong-only-live').checked=kind==='wrong';
  for(const button of document.querySelectorAll('[data-strategy]'))button.setAttribute('aria-pressed',String(button.dataset.strategy===kind));
  clearTimeout(searchDebounce);page=1;refreshSamples();
}
function renderBatchState(){
  const state=batchPhase(current,Date.now()+serverClockOffsetMs);
  $('batch-rail').dataset.stage=state.id;
  $('batch-stage').textContent=state.title;
  const primary=$('hero-primary-action');
  primary.href=state.canVote?'#explore':state.id==='published'?'#results-section':'#batch-rail';
  primary.replaceChildren(document.createTextNode(state.canVote?'学習データを探す ':state.id==='published'?'学習結果を見る ':'処理状況を確認 '));
  const symbol=document.createElement('span');symbol.setAttribute('aria-hidden','true');symbol.textContent='↗';primary.append(symbol);
  $('batch-description').textContent=state.description;
  for(const [id,value] of [
    ['batch-voter-count',voteSummary?.voter_count],
    ['batch-pick-count',voteSummary?.vote_count],
    ['batch-forecast-count',voteSummary?.forecast_count],
  ]){
    $(id).textContent=Number.isInteger(value)?value.toLocaleString('ja-JP'):'—';
  }
  const due=Number(current?.closes_at);
  $('batch-fixed-deadline').textContent=Number.isFinite(due)&&due>0?
    `投票の締切：${new Date(due*1000).toLocaleString('ja-JP',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}`:
    '投票の締切：未定';
  const order=['vote','lock','train','publish'];
  const selected={voting:0,'awaiting-lock':1,locked:1,training:2,published:3}[state.id]??-1;
  document.querySelectorAll('[data-batch-step]').forEach((element,index)=>{
    element.dataset.state=index===selected?'current':index<selected?'complete':'upcoming';
    element.setAttribute('aria-current',index===selected?'step':'false');
  });
}
function syncControls(){
  const statusNow=deadline();
  const editable=statusNow.isOpen;
  $('round-countdown').textContent=statusNow.label;
  $('sample-id').disabled=!editable;
  $('id-form-live').querySelector('button').disabled=!editable;
  $('save-reason').disabled=!editable;$('reason-live').disabled=!editable;
  $('pool-caption').textContent=editable?'推薦を受付中':current?'推薦の受付は終了しています':'学習データ未準備';
  const phase=$('round-phase');
  const phases={OPEN:'推薦受付中：画像カードから選ぶと即時保存されます。',LOCKED:'投票終了：結果の集計・追加学習を準備中です。',TRAINING:'追加学習中：推薦は変更できません。',PUBLISHED:'結果公開済み：次のクエストを確認してください。'};
  phase.textContent=current?(current.status==='OPEN'&&!editable?'締切時刻を過ぎました。集計処理を待っています。':
    (phases[current.status]||`現在の状態：${current.status}。推薦は変更できません。`)):'モデル未初期化：推薦はまだできません。';
  phase.dataset.phase=editable?'open':'closed';
  renderBatchState();syncForecastControls();updateGameProgress();
}
function renderModel(info){
  current=info.round;
  voteSummary=info.vote_summary||null;
  if(Number.isFinite(info.server_time))serverClockOffsetMs=info.server_time*1000-Date.now();
  const mode=info.mode;datasetName=info.dataset_name||null;
  $('mode-badge').className='mode-tag '+(mode==='LIVE'?'is-live':'is-warning');
  $('mode-badge').replaceChildren();
  const led=document.createElement('span');led.className='status-led';led.setAttribute('aria-hidden','true');$('mode-badge').append(led,document.createTextNode(mode==='LIVE'?' LIVE · 実測値':mode==='DEMO'?' DEMO · 合成画像の実測':' 未初期化 / 未接続'));
  updateQuest(current?.targets,current?.id||'ROUND —');
  $('metric-round').textContent=current?.id||'—';
  const metrics=info.metrics?.public;
  setMetric(metrics?.overall_loss,'metric-loss',n=>n.toFixed(3));
  setMetric(metrics?.accuracy,'metric-accuracy',n=>(100*n).toFixed(1)+'%');
  const intel=questIntel(metrics,current?.targets);
  $('quest-recall-a').textContent=intel[0]?`${intel[0].label} ${intel[0].recall}`:'—';
  $('quest-recall-b').textContent=intel[1]?`${intel[1].label} ${intel[1].recall}`:'—';
  $('strategy-a').textContent=intel[0]?`${intel[0].label}の画像`:'弱点Aの画像';
  $('strategy-b').textContent=intel[1]?`${intel[1].label}の画像`:'弱点Bの画像';
  syncControls();
  if(!current)setSystemMessage('初期モデルと学習データがまだ登録されていません。サーバー管理者による初期化が必要です。','warning');
  else if(!metrics)setSystemMessage('検証結果が未計測です。推測値を代わりに表示することはありません。','warning');
  else if(current.status!=='OPEN')setSystemMessage(`現在は ${current.status} フェーズです。学習が終わるまで推薦を変更できません。`,'warning');
  else if(mode==='DEMO')setSystemMessage('合成ピクセルアートを使う技術デモです。実際にAIが学習しますが、CIFAR-10の性能結果ではありません。','warning');
  else setSystemMessage('モデルの実測データを表示しています。選んだ画像は投票締切後の学習に反映されます。');
}
async function refreshPicks(){
  if(!current){picks=new Set();drawPicks();return;}
  // Keep the previous selection if a transient request fails.
  const value=await request(`/v1/rounds/${encodeURIComponent(current.id)}/picks/me`);
  picks=new Set(value.ids);if(!noteDirty)$('reason-live').value=value.note||'';drawPicks();
}
function drawPicks(){
  renderPicks([...picks].sort((a,b)=>a-b),{disabled:!deadline().isOpen,onRemove:id=>vote(id,false)});
  updateGameProgress();
}
function queryValue(){
  const q=$('query').value.trim();const ix=CLASS_NAMES.indexOf(q);return ix>=0?CLASS_KEYS[ix]:q;
}
function syncPagination(limit=pageSize()){
  const atStart=page<=1,atEnd=page*limit>=total;
  $('prev-page').disabled=atStart;$('prev-page-bottom').disabled=atStart;
  $('next-page').disabled=atEnd;$('next-page-bottom').disabled=atEnd;
  $('bottom-page-label').textContent=`ページ ${page} / ${Math.max(1,Math.ceil(total/limit))}`;
}
function focusExplorer(){
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  $('explore').scrollIntoView({behavior:reduced?'auto':'smooth',block:'start'});
  $('page-caption').focus({preventScroll:true});
}
function showEmpty(title,description,action){
  $('empty-heading').textContent=title;$('empty-description').textContent=description;
  $('empty-action').textContent=action==='retry'?'もう一度読み込む':'検索条件をクリア';
  $('empty-action').dataset.action=action;
  $('empty-state').hidden=false;
}
function resetFilters(){
  clearTimeout(searchDebounce);$('query').value='';$('label-filter').value='';$('wrong-only-live').checked=false;
  page=1;return refreshSamples();
}
async function refreshSamples(){
  const key=++requestVersion;
  const grid=$('sample-grid');
  if(!current){grid.replaceChildren();total=0;syncPagination();$('page-caption').textContent='学習開始待ち';showEmpty('まだ学習が始まっていません','管理者によるモデルとデータの初期化後に画像を探索できます。','retry');return;}
  const limit=pageSize();
  const params=new URLSearchParams({page:String(page),limit:String(limit)});
  if($('label-filter').value)params.set('label',$('label-filter').value);
  if($('wrong-only-live').checked)params.set('wrong_only','true');
  if(queryValue())params.set('query',queryValue());
  grid.classList.add('is-loading');grid.setAttribute('aria-busy','true');
  $('page-caption').textContent='画像を読み込み中…';$('empty-state').hidden=true;
  try{
    const data=await request('/v1/samples?'+params.toString());if(key!==requestVersion)return;
    total=data.total;
    $('dataset-rights').textContent=data.image_kind==='SYNTHETIC_PIXEL_ART'?
      'ⓘ この画像は独自生成した合成ピクセルアートです。CIFAR-10画像ではありません。':
      data.image_rights_approved?'ⓘ 権利確認済みの画像を表示しています。':
      'ⓘ 画像公開の許可が未確認です。画像の代替ビジュアルを表示しています。';
    grid.replaceChildren(...data.items.map(item=>createSampleCard({...item,image_kind:data.image_kind,selected:picks.has(item.id),disabled:!deadline().isOpen||(!picks.has(item.id)&&picks.size>=10),onToggle:vote})));
    if(!data.items.length && total>0 && page>1){page=Math.max(1,Math.ceil(total/limit));return refreshSamples();}
    if(!data.items.length)showEmpty('一致するデータがありません','画像ID・クラス・誤分類条件を変更してみてください。','reset');
    const start=data.items.length?(page-1)*limit+1:0;
    $('page-caption').textContent=`${total.toLocaleString('ja-JP')} 件中 ${start}–${(page-1)*limit+data.items.length} 件表示${data.predictions_stale?' · 予測未計測':''}`;
    syncPagination(limit);
    $('explorer-error')?.remove();
  }catch(error){
    if(key!==requestVersion)return;
    grid.replaceChildren();
    $('page-caption').textContent='画像を取得できませんでした';
    showEmpty('データを取得できません',`通信またはモデルの準備状況を確認してください。${error.message}`,'retry');
    $('prev-page').disabled=true;$('next-page').disabled=true;$('prev-page-bottom').disabled=true;$('next-page-bottom').disabled=true;
  }finally{
    if(key===requestVersion){grid.classList.remove('is-loading');grid.removeAttribute('aria-busy');}
  }
}
async function vote(id,add=true){
  if(!deadline().isOpen){status('推薦受付は終了しました。結果の公開をお待ちください。','error');return false;}
  if(!Number.isInteger(id)||id<0){status('有効な画像IDを指定してください。','error');return false;}
  if(add&&picks.size>=10&&!picks.has(id)){status('最大10枚です。先に別の画像を解除してください。','error');return false;}
  if(busy){status('前の推薦を処理中です。','info');return false;}
  const oldFocus=document.activeElement;
  const fromCard=oldFocus?.dataset?.pickId===String(id);
  const fromList=oldFocus?.dataset?.removeId===String(id);
  busy=true;status('推薦をサーバーへ保存しています…');
  try{
    await request(`/v1/rounds/${encodeURIComponent(current.id)}/picks/${id}`,{method:add?'PUT':'DELETE'});
    let refreshed=true;
    try{await refreshPicks();await refreshSamples();}
    catch(error){refreshed=false;status('推薦は保存されましたが、表示更新に失敗しました。「最新の状態に更新」を押してください。','warning');}
    if(refreshed){
      status(add?`画像 #${id} の推薦をサーバーに保存しました。締切前は解除できます。`:`画像 #${id} の推薦解除をサーバーに保存しました。`,'success');
      if(fromCard)document.querySelector(`[data-pick-id="${id}"]`)?.focus({preventScroll:true});
      if(fromList){
        const removeButton=$('my-picks').querySelector('button:not(:disabled)');
        if(removeButton)removeButton.focus({preventScroll:true});
        else $('vote-status').focus({preventScroll:true});
      }
    }
    return true;
  }catch(error){
    status(`推薦を保存できませんでした：${error.message}。選択は反映されていません。再試行してください。`,'error');
    return false;
  }finally{busy=false;}
}
async function refreshResults(){
  try{
    const history=await request('/v1/rounds/history');
    const published=history.items.find(item=>item.status==='PUBLISHED');
    if(!published){lastPublished=false;renderResults(null);updateGameProgress();return;}
    const result=await request(`/v1/rounds/${encodeURIComponent(published.id)}/results`);
    lastPublished=Boolean(result.results);renderResults(result.results||null);updateGameProgress();
  }catch(error){$('results').textContent='結果の取得に失敗しました：'+error.message;}
}
async function refreshAll(){
  const info=await request('/v1/rounds/current');
  const prior=current?.id;renderModel(info);
  $('service-fallback').hidden=true;
  if(prior!==current?.id){page=1;forecastPct=null;forecastDirty=false;}
  // Refresh remote picks even when the round didn't change (other tabs or devices).
  await refreshPicks();
  await Promise.all([refreshSamples(),refreshResults(),refreshForecast()]);
}
function searchNow(){clearTimeout(searchDebounce);page=1;refreshSamples();}
for(const btn of document.querySelectorAll('[data-strategy]')){
  btn.setAttribute('aria-pressed','false');
  btn.addEventListener('click',()=>applyStrategy(btn.dataset.strategy));
}
$('forecast-range').addEventListener('input',()=>{
  forecastDirty=true;
  const percent=Number($('forecast-range').value);
  $('forecast-pct').textContent=`${percent}%`;
  $('forecast-hint').textContent=forecastHint(percent);
  $('forecast-status').textContent='まだ保存されていません。「予測を保存」を押すと確定します。';
  $('forecast-status').dataset.level='info';
});
$('forecast-form').addEventListener('submit',async event=>{
  event.preventDefault();
  if(!current||!deadline().isOpen||forecastBusy)return;
  forecastBusy=true;syncForecastControls();
  const percent=Number($('forecast-range').value);
  $('forecast-status').textContent=`${percent}% の予測をサーバーへ保存中…`;
  try{
    await request(`/v1/rounds/${encodeURIComponent(current.id)}/forecast/me`,{
      method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({probability_pct:percent})});
    forecastPct=percent;forecastDirty=false;
    $('forecast-status').dataset.level='success';
    $('forecast-status').textContent=`${percent}% で予測を保存しました。締切前なら変更できます。`;
    updateGameProgress();
    const rec=await request('/v1/game/me');renderForecastRecord(rec);
  }catch(error){
    $('forecast-status').dataset.level='error';
    $('forecast-status').textContent='予測を保存できませんでした：'+error.message+'。入力値は残っています。';
  }finally{forecastBusy=false;syncForecastControls();}
});
$('filters').addEventListener('submit',e=>{e.preventDefault();searchNow();});
$('query').addEventListener('input',()=>{clearTimeout(searchDebounce);searchDebounce=setTimeout(searchNow,300);});
$('label-filter').addEventListener('change',searchNow);
$('wrong-only-live').addEventListener('change',searchNow);
$('prev-page').addEventListener('click',()=>{if(page>1){page--;refreshSamples();}});
$('next-page').addEventListener('click',()=>{if(page*pageSize()<total){page++;refreshSamples();}});
$('prev-page-bottom').addEventListener('click',()=>{if(page>1){page--;refreshSamples();focusExplorer();}});
$('next-page-bottom').addEventListener('click',()=>{if(page*pageSize()<total){page++;refreshSamples();focusExplorer();}});
$('empty-action').addEventListener('click',()=>{
  if($('empty-action').dataset.action!=='retry'){resetFilters();return;}
  if(current)refreshSamples();
  else refreshAll().catch(err=>{$('service-fallback').hidden=false;setSystemMessage('サーバーに接続できません：'+err.message,'warning');});
});
$('id-form-live').addEventListener('submit',async e=>{
  e.preventDefault();const input=$('sample-id');const raw=input.value.trim();
  if(!/^\d+$/.test(raw)||!Number.isSafeInteger(Number(raw))){
    status('画像IDは半角数字の0以上の整数で入力してください。','error');return;
  }
  if(await vote(Number(raw),true))input.value='';
});
$('reason-live').addEventListener('input',()=>{noteDirty=true;$('note-state').textContent='未保存のメモがあります。推薦操作をしても内容は消えません。';});
$('save-reason').addEventListener('click',async()=>{
  if(!current)return;
  const button=$('save-reason');button.disabled=true;
  try{await request(`/v1/rounds/${encodeURIComponent(current.id)}/note`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('reason-live').value})});noteDirty=false;$('note-state').textContent='メモを保存しました。';status('推薦理由のメモをサーバーに保存しました。','success');}
  catch(e){$('note-state').textContent='メモは未保存です。再試行してください。';status('メモを保存できませんでした：'+e.message+'。入力内容は残っています。','error');}
  finally{button.disabled=!deadline().isOpen;}
});
$('refresh').addEventListener('click',()=>refreshAll().catch(err=>{$('service-fallback').hidden=false;setSystemMessage('更新に失敗：'+err.message,'warning');}));
let lastLimit=pageSize();
window.addEventListener('resize',()=>{const next=pageSize();if(next!==lastLimit){lastLimit=next;page=1;refreshSamples();}},{passive:true});
setupMobileVoteLink();
refreshAll().catch(error=>{$('service-fallback').hidden=false;setSystemMessage('サーバーAPIに接続できません：'+error.message,'warning');$('pool-caption').textContent='接続待ち';syncControls();$('sample-grid').replaceChildren();showEmpty('サーバーに接続できません','通信状態を確認し、もう一度読み込んでください。','retry');$('page-caption').textContent='接続待ち';});

// Countdown is quiet for assistive technologies; announce only a state transition.
lastEditable=deadline().isOpen;
setInterval(()=>{
  if(!current)return;
  const editable=deadline().isOpen;
  $('round-countdown').textContent=deadline().label;
  renderBatchState();
  if(editable!==lastEditable){
    lastEditable=editable;syncControls();drawPicks();refreshSamples();
    if(!editable)status('投票締切になりました。次のラウンドの結果をお待ちください。','info');
  }
},1000);
// Keep the phase and results up-to-date without requiring a manual refresh.
setInterval(()=>{
  if(document.visibilityState==='hidden'||busy||autoRefreshing)return;
  autoRefreshing=true;
  refreshAll().catch(e=>setSystemMessage('自動更新に失敗しました。「最新の状態に更新」から再試行してください：'+e.message,'warning'))
    .finally(()=>{autoRefreshing=false;lastEditable=deadline().isOpen;});
},15000);
