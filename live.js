import {CLASS_NAMES,CLASS_KEYS,$,renderPicks,setSystemMessage,createSampleCard,updateQuest,setMetric,renderResults,setupMobileVoteLink} from './src/arena-view.js';
let current=null;let picks=new Set();let page=1,total=0;let busy=false;let requestVersion=0;
let searchDebounce=null;let noteDirty=false;
for(let i=0;i<CLASS_NAMES.length;i++){
  const option=document.createElement('option');option.value=String(i);option.textContent=CLASS_NAMES[i];$('label-filter').append(option);
}
function status(text,level='info'){$('vote-status').textContent=text;$('vote-status').dataset.level=level;}
function pageSize(){return window.innerWidth<=620?12:window.innerWidth<=850?24:48;}
async function request(url,options={}){
  const response=await fetch(url,{credentials:'same-origin',cache:'no-store',...options});
  let data;try{data=await response.json();}catch{throw Error(`サーバーの応答形式に問題があります（HTTP ${response.status}）`);}
  if(!response.ok)throw Error(typeof(data.error||data.detail)==='string'?(data.error||data.detail):`HTTP ${response.status}`);
  return data;
}
function syncControls(){
  const editable=current?.status==='OPEN';
  $('sample-id').disabled=!editable;
  $('id-form-live').querySelector('button').disabled=!editable;
  $('save-reason').disabled=!editable;$('reason-live').disabled=!editable;
  $('pool-caption').textContent=editable?'推薦を受付中':current?'推薦の受付は終了しています':'学習データ未準備';
  const phase=$('round-phase');
  const phases={OPEN:'推薦受付中：画像カードから選ぶと即時保存されます。',LOCKED:'投票終了：結果の集計・追加学習を準備中です。',TRAINING:'追加学習中：推薦は変更できません。',PUBLISHED:'結果公開済み：次のクエストを確認してください。'};
  phase.textContent=current?(phases[current.status]||`現在の状態：${current.status}。推薦は変更できません。`):'モデル未初期化：推薦はまだできません。';
  phase.dataset.phase=editable?'open':'closed';
}
function renderModel(info){
  current=info.round;
  const mode=info.mode;
  $('mode-badge').className='mode-tag '+(mode==='LIVE'?'is-live':'is-warning');
  $('mode-badge').replaceChildren();
  const led=document.createElement('span');led.className='status-led';led.setAttribute('aria-hidden','true');$('mode-badge').append(led,document.createTextNode(mode==='LIVE'?' LIVE · 実測値':' 未初期化 / 未接続'));
  updateQuest(current?.targets,current?.id||'ROUND —');
  $('metric-round').textContent=current?.id||'—';
  const metrics=info.metrics?.public;
  setMetric(metrics?.overall_loss,'metric-loss',n=>n.toFixed(3));
  setMetric(metrics?.accuracy,'metric-accuracy',n=>(100*n).toFixed(1)+'%');
  syncControls();
  if(!current)setSystemMessage('初期モデルと学習データがまだ登録されていません。サーバー管理者による初期化が必要です。','warning');
  else if(!metrics)setSystemMessage('検証結果が未計測です。推測値を代わりに表示することはありません。','warning');
  else if(current.status!=='OPEN')setSystemMessage(`現在は ${current.status} フェーズです。学習が終わるまで推薦を変更できません。`,'warning');
  else setSystemMessage('モデルの実測データを表示しています。選んだ画像は投票締切後の学習に反映されます。');
}
async function refreshPicks(){
  if(!current){picks=new Set();drawPicks();return;}
  // Keep the previous selection if a transient request fails.
  const value=await request(`/v1/rounds/${encodeURIComponent(current.id)}/picks/me`);
  picks=new Set(value.ids);if(!noteDirty)$('reason-live').value=value.note||'';drawPicks();
}
function drawPicks(){
  renderPicks([...picks].sort((a,b)=>a-b),{disabled:current?.status!=='OPEN',onRemove:id=>vote(id,false)});
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
    $('dataset-rights').textContent=data.image_rights_approved?
      'ⓘ 権利確認済みの画像を表示しています。':
      'ⓘ 画像公開の許可が未確認です。画像の代替ビジュアルを表示しています。';
    grid.replaceChildren(...data.items.map(item=>createSampleCard({...item,selected:picks.has(item.id),disabled:current.status!=='OPEN'||(!picks.has(item.id)&&picks.size>=10),onToggle:vote})));
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
  if(!current||current.status!=='OPEN'){status('投票受付中のラウンドでのみ変更できます。','error');return false;}
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
    if(!published){renderResults(null);return;}
    const result=await request(`/v1/rounds/${encodeURIComponent(published.id)}/results`);
    renderResults(result.results||null);
  }catch(error){$('results').textContent='結果の取得に失敗しました：'+error.message;}
}
async function refreshAll(){
  const info=await request('/v1/rounds/current');
  const prior=current?.id;renderModel(info);
  if(prior!==current?.id)page=1;
  // Refresh remote picks even when the round didn't change (other tabs or devices).
  await refreshPicks();
  await Promise.all([refreshSamples(),refreshResults()]);
}
function searchNow(){clearTimeout(searchDebounce);page=1;refreshSamples();}
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
  else refreshAll().catch(err=>setSystemMessage('サーバーに接続できません：'+err.message,'warning'));
});
$('id-form-live').addEventListener('submit',async e=>{
  e.preventDefault();const input=$('sample-id');const raw=input.value.trim();
  if(raw===''){status('画像IDを入力してください。','error');return;}
  if(await vote(Number(raw),true))input.value='';
});
$('reason-live').addEventListener('input',()=>{noteDirty=true;$('note-state').textContent='未保存のメモがあります。推薦操作をしても内容は消えません。';});
$('save-reason').addEventListener('click',async()=>{
  if(!current)return;
  const button=$('save-reason');button.disabled=true;
  try{await request(`/v1/rounds/${encodeURIComponent(current.id)}/note`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('reason-live').value})});noteDirty=false;$('note-state').textContent='メモを保存しました。';status('推薦理由のメモをサーバーに保存しました。','success');}
  catch(e){$('note-state').textContent='メモは未保存です。再試行してください。';status('メモを保存できませんでした：'+e.message+'。入力内容は残っています。','error');}
  finally{button.disabled=current?.status!=='OPEN';}
});
$('refresh').addEventListener('click',()=>refreshAll().catch(err=>setSystemMessage('更新に失敗：'+err.message,'warning')));
let lastLimit=pageSize();
window.addEventListener('resize',()=>{const next=pageSize();if(next!==lastLimit){lastLimit=next;page=1;refreshSamples();}},{passive:true});
setupMobileVoteLink();
refreshAll().catch(error=>{setSystemMessage('サーバーAPIに接続できません：'+error.message,'warning');$('pool-caption').textContent='接続待ち';syncControls();$('sample-grid').replaceChildren();showEmpty('サーバーに接続できません','通信状態を確認し、もう一度読み込んでください。','retry');$('page-caption').textContent='接続待ち';});
