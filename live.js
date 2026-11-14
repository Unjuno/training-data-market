const $=id=>document.getElementById(id);
const CLASS_NAMES=['飛行機','自動車','鳥','猫','鹿','犬','カエル','馬','船','トラック'];
const CLASS_KEYS=['airplane','automobile','bird','cat','deer','dog','frog','horse','ship','truck'];
let round=null,myPicks=new Set(),page=1,total=0,rights=false,loading=false;

for (let i=0;i<10;i++) {
  const option=document.createElement('option');option.value=String(i);option.textContent=CLASS_NAMES[i];
  $('label-filter').append(option);
}
function msg(text,type='info') {$('app-alert').textContent=text;$('app-alert').dataset.level=type;}
function message(text) {$('vote-status').textContent=text;}
async function request(path, options={}) {
  const response=await fetch(path,{credentials:'same-origin',cache:'no-store',...options});
  let body;
  try {body=await response.json();}catch {throw new Error(`APIから不正な応答（HTTP ${response.status}）`);}
  if(!response.ok)throw new Error(body.error||body.detail||`HTTP ${response.status}`);
  return body;
}
const text=(parent,tag,value,cls)=>{const el=document.createElement(tag);el.textContent=value;if(cls)el.className=cls;parent.append(el);return el;};
function setState(roundResponse) {
  const {round:current,metrics,mode}=roundResponse;
  round=current;
  $('metric-round').textContent=current?.id||'—';
  $('target-pair').textContent=current?.targets?current.targets.map(i=>CLASS_NAMES[i]).join(' × '):'未設定';
  $('mode-badge').textContent=mode==='LIVE'?'LIVE · 実測値':mode==='UNINITIALIZED'?'未初期化':'接続状態不明';
  $('mode-badge').className='pill '+(mode==='LIVE'?'green':'amber');
  const pub=metrics?.public;
  $('metric-loss').textContent=pub?pub.overall_loss.toFixed(3):'—';
  $('metric-accuracy').textContent=pub?(100*pub.accuracy).toFixed(1)+'%':'—';
  const open=current?.status==='OPEN';
  $('sample-id').disabled=!open;
  $('id-form-live').querySelector('button').disabled=!open;
  $('reason-live').disabled=!open; $('save-reason').disabled=!open;
  $('pool-caption').textContent=open?'推薦受付中':'推薦受付停止中';
  if(!current){msg('学習用データと初期チェックポイントが未準備です。運営者がCIFAR-10をセットアップすると開始できます。','warning');}
  else if (!pub){msg('モデルの検証指標を取得できません。未計測の値は表示しません。','warning');}
  else if (!open){msg(`ラウンド ${current.id} は ${current.status} です。学習完了まで推薦は変更できません。`,'warning');}
  else {msg('実測値に基づいて学習候補を推薦できます。推薦は締切後の学習で反映されます。');}
}
async function refreshRound() {
  const value=await request('/v1/rounds/current');
  const old=round?.id;
  setState(value);
  if(old!==round?.id){page=1;await refreshPicks();}
  await Promise.all([refreshSamples(),refreshResults()]);
}
async function refreshPicks() {
  myPicks=new Set();
  if(!round){renderPicks();return;}
  try {const value=await request(`/v1/rounds/${encodeURIComponent(round.id)}/picks/me`);myPicks=new Set(value.ids);$('reason-live').value=value.note||'';}
  catch(error){message(error.message);}
  renderPicks();
}
function renderPicks() {
  $('my-count').textContent=`${myPicks.size} / 10`;
  $('my-picks').replaceChildren();
  if(!myPicks.size){text($('my-picks'),'li','まだ推薦がありません','muted');return;}
  for(const id of [...myPicks].sort((a,b)=>a-b)) {
    const li=document.createElement('li');li.className='pick-chip';text(li,'span',`#${id}`);
    const btn=text(li,'button','取消');btn.type='button';btn.disabled=round?.status!=='OPEN';btn.setAttribute('aria-label',`画像${id}の推薦を解除`);
    btn.addEventListener('click',()=>vote(id,false));$('my-picks').append(li);
  }
}
async function vote(id, add=true) {
  if(!round||round.status!=='OPEN'){message('推薦は受付中のラウンドでのみ可能です。');return;}
  if(!Number.isInteger(id)||id<0){message('有効な画像IDを入力してください。');return;}
  if(loading)return;
  loading=true;
  try {
    await request(`/v1/rounds/${encodeURIComponent(round.id)}/picks/${id}`,{method:add?'PUT':'DELETE'});
    await refreshPicks();await refreshSamples();
    message(add?`画像 #${id} の推薦をサーバーで受け付けました。`:`画像 #${id} の推薦を取り消しました。`);
  }catch(error){message(`操作失敗：${error.message}`);}
  finally {loading=false;}
}
function makeCard(item) {
  const article=document.createElement('article');article.className='sample-card';
  const art=document.createElement('div');art.className='sample-art live-art';
  if(item.image_url){const img=document.createElement('img');img.src=item.image_url;img.alt=`${CLASS_NAMES[item.label]}の学習候補 #${item.id}`;img.loading='lazy';img.width=96;img.height=96;art.append(img);}
  else {text(art,'span','画像未公開');}
  article.append(art);
  const top=document.createElement('div');top.className='sample-top';text(top,'span',`#${item.id}`,'sample-id');
  const isWrong=!!(item.prediction&&item.prediction.predicted!==item.label);
  text(top,'span',item.prediction?(isWrong?'誤分類':'正解'):'未推論',isWrong?'error-tag':'ok-tag');article.append(top);
  text(article,'h3',CLASS_NAMES[item.label],'sample-label');
  text(article,'p',item.prediction?`AIの予測：${CLASS_NAMES[item.prediction.predicted]}`:'AIの予測：未計測','sample-pred');
  const bottom=document.createElement('div');bottom.className='sample-bottom';
  text(bottom,'span',`Loss ${item.prediction?item.prediction.loss.toFixed(3):'—'} · ${item.votes}票`);
  const active=myPicks.has(item.id);
  const btn=text(bottom,'button',active?'推薦取消':'推薦する','select-button');btn.type='button';
  btn.setAttribute('aria-pressed',String(active));btn.disabled=round?.status!=='OPEN';
  btn.addEventListener('click',()=>vote(item.id,!active));article.append(bottom);return article;
}
async function refreshSamples() {
  const grid=$('sample-grid');grid.replaceChildren();
  if(!round){$('page-caption').textContent='利用可能な候補がありません。';return;}
  const params=new URLSearchParams({page:String(page),limit:'48'});
  if($('label-filter').value!=='')params.set('label',$('label-filter').value);
  if($('wrong-only-live').checked)params.set('wrong_only','true');
  if($('query').value.trim())params.set('query',$('query').value.trim());
  try {
    const r=await request('/v1/samples?'+params.toString());total=r.total;rights=r.image_rights_approved;
    $('dataset-rights').textContent=rights?'画像公開が許可された候補を表示しています。':'公開権利が未承認のため、画像本体は表示していません。';
    grid.replaceChildren(...r.items.map(makeCard));
    $('empty-state').hidden=r.items.length!==0;
    $('page-caption').textContent=`全${total}件 / ${page}ページ目（最大48件ずつ）${r.predictions_stale?' · 損失未更新':''}`;
    $('prev-page').disabled=page<=1;$('next-page').disabled=page*48>=total;
  }catch(error){$('page-caption').textContent='データの取得に失敗：'+error.message;}
}
async function refreshResults() {
  try {
    const list=await request('/v1/rounds/history');
    const published=list.items.find(item=>item.status==='PUBLISHED');
    if(!published)return;
    const data=await request(`/v1/rounds/${published.id}/results`);
    const r=data.results;if(!r)return;
    const content=$('results');content.replaceChildren();
    text(content,'p',`${r.round_id} · ${r.target_pair.map(i=>CLASS_NAMES[i]).join(' × ')}`,'eyebrow');
    const table=document.createElement('table');table.className='live-table';
    const rows=[['対象Loss','学習前','投票モデル','ランダムモデル'],
       ['値',r.before.target_loss.toFixed(4),r.community.target_loss.toFixed(4),r.random.target_loss.toFixed(4)],
       ['改善量','—',(r.before.target_loss-r.community.target_loss).toFixed(4),(r.before.target_loss-r.random.target_loss).toFixed(4)]];
    for(const row of rows){const tr=document.createElement('tr');for(const val of row)text(tr,'td',val);table.append(tr);}content.append(table);
    text(content,'p',`共有モデルへの採用：${r.promotion==='community'?'投票モデル':r.promotion==='random'?'ランダム対照':'更新せず（ロールバック）'}`);
    text(content,'p',`投票由来 ${r.voted_count}枚／全128枚・両アーム各40更新ステップ`,'small muted');
  }catch(error){$('results').textContent='結果を取得できません：'+error.message;}
}
$('filters').addEventListener('submit',ev=>{ev.preventDefault();page=1;refreshSamples();});
$('prev-page').addEventListener('click',()=>{if(page>1){page--;refreshSamples();}});
$('next-page').addEventListener('click',()=>{if(page*48<total){page++;refreshSamples();}});
$('id-form-live').addEventListener('submit',ev=>{ev.preventDefault();const id=Number($('sample-id').value);vote(id,true);$('sample-id').value='';});
$('save-reason').addEventListener('click',async()=>{if(!round)return;try{await request(`/v1/rounds/${round.id}/note`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('reason-live').value})});message('推薦理由を保存しました。');}catch(e){message('保存に失敗：'+e.message);}});
$('refresh').addEventListener('click',()=>refreshRound().catch(err=>msg('取得エラー：'+err.message,'warning')));
refreshRound().catch(error=>msg('APIに接続できません：'+error.message,'warning'));
