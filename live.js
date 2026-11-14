import {CLASS_NAMES,CLASS_KEYS,$,renderPicks,setSystemMessage,createSampleCard,updateQuest,setMetric,renderResults,setupMobileVoteLink} from './src/arena-view.js';
let current=null;let picks=new Set();let page=1,total=0;let busy=false;let requestVersion=0;
for(let i=0;i<CLASS_NAMES.length;i++){
  const option=document.createElement('option');option.value=String(i);option.textContent=CLASS_NAMES[i];$('label-filter').append(option);
}
function status(text){$('vote-status').textContent=text;}
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
  $('pool-caption').textContent=editable?'投票受付中':'投票受付停止';
}
function renderModel(info){
  current=info.round;
  const mode=info.mode;
  $('mode-badge').className='mode-tag '+(mode==='LIVE'?'is-live':'is-warning');
  $('mode-badge').innerHTML='';
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
  else setSystemMessage('表示中の値は現在の共有AIの実測データです。推薦は締切後の学習に反映されます。');
}
async function refreshPicks(){
  picks=new Set();if(!current){drawPicks();return;}
  const value=await request(`/v1/rounds/${encodeURIComponent(current.id)}/picks/me`);
  picks=new Set(value.ids);$('reason-live').value=value.note||'';drawPicks();
}
function drawPicks(){
  renderPicks([...picks].sort((a,b)=>a-b),{disabled:current?.status!=='OPEN',onRemove:id=>vote(id,false)});
}
function queryValue(){
  const q=$('query').value.trim();const ix=CLASS_NAMES.indexOf(q);return ix>=0?CLASS_KEYS[ix]:q;
}
async function refreshSamples(){
  const key=++requestVersion;
  const grid=$('sample-grid');
  if(!current){grid.replaceChildren();$('page-caption').textContent='利用可能なデータなし';return;}
  const params=new URLSearchParams({page:String(page),limit:'48'});
  if($('label-filter').value)params.set('label',$('label-filter').value);
  if($('wrong-only-live').checked)params.set('wrong_only','true');
  if(queryValue())params.set('query',queryValue());
  try{
    const data=await request('/v1/samples?'+params.toString());if(key!==requestVersion)return;
    total=data.total;
    $('dataset-rights').textContent=data.image_rights_approved?
      'ⓘ 権利確認済みのCIFAR-10画像を表示しています。':
      'ⓘ 画像公開の許可が未確認です。代替ビジュアルを表示しています。';
    grid.replaceChildren(...data.items.map(item=>createSampleCard({...item,selected:picks.has(item.id),disabled:current.status!=='OPEN'||(!picks.has(item.id)&&picks.size>=10),onToggle:vote})));
    $('empty-state').hidden=data.items.length>0;
    $('page-caption').textContent=`${total.toLocaleString('ja-JP')} 件中 ${(page-1)*48+Math.min(1,data.items.length)}–${(page-1)*48+data.items.length} 件表示${data.predictions_stale?' · Loss未更新':''}`;
    $('prev-page').disabled=page<=1;$('next-page').disabled=page*48>=total;
    $('explorer-error')?.remove();
  }catch(error){if(key!==requestVersion)return;grid.replaceChildren();$('empty-state').hidden=false;$('page-caption').textContent='取得失敗：'+error.message;}
}
async function vote(id,add=true){
  if(!current||current.status!=='OPEN'){status('投票受付中のラウンドでのみ変更できます。');return;}
  if(!Number.isInteger(id)||id<0){status('有効な画像IDを指定してください。');return;}
  if(add&&picks.size>=10&&!picks.has(id)){status('推薦できるのは最大10枚です。先に別の画像を解除してください。');return;}
  if(busy)return;busy=true;
  try{
    await request(`/v1/rounds/${encodeURIComponent(current.id)}/picks/${id}`,{method:add?'PUT':'DELETE'});
    await refreshPicks();await refreshSamples();
    status(add?`画像 #${id} を推薦しました。`:`画像 #${id} の推薦を解除しました。`);
  }catch(error){status(`更新できませんでした：${error.message}`);}
  finally{busy=false;}
}
async function refreshResults(){
  try{
    const history=await request('/v1/rounds/history');
    const published=history.items.find(item=>item.status==='PUBLISHED');
    if(!published){renderResults(null);return;}
    const result=await request(`/v1/rounds/${encodeURIComponent(published.id)}/results`);
    renderResults(result.results||null);
  }catch(error){$('results').textContent='結果の取得に失敗：'+error.message;}
}
async function refreshAll(){
  const info=await request('/v1/rounds/current');
  const prior=current?.id;renderModel(info);
  if(prior!==current?.id){page=1;await refreshPicks();}
  await Promise.all([refreshSamples(),refreshResults()]);
}
$('filters').addEventListener('submit',e=>{e.preventDefault();page=1;refreshSamples();});
$('prev-page').addEventListener('click',()=>{if(page>1){page--;refreshSamples();}});
$('next-page').addEventListener('click',()=>{if(page*48<total){page++;refreshSamples();}});
$('id-form-live').addEventListener('submit',e=>{e.preventDefault();const id=Number($('sample-id').value);if($('sample-id').value.trim()!=='')vote(id,true);$('sample-id').value='';});
$('save-reason').addEventListener('click',async()=>{if(!current)return;try{await request(`/v1/rounds/${encodeURIComponent(current.id)}/note`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('reason-live').value})});status('推薦理由をサーバーへ保存しました。');}catch(e){status('保存失敗：'+e.message);}});
$('refresh').addEventListener('click',()=>refreshAll().catch(err=>setSystemMessage('更新に失敗：'+err.message,'warning')));
setupMobileVoteLink();
refreshAll().catch(error=>{setSystemMessage('サーバーAPIに接続できません：'+error.message,'warning');$('pool-caption').textContent='接続待ち';syncControls();});
