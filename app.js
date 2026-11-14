import {DEMO_SAMPLES} from './src/demo-data.js';
import {filterSamples,addPick,togglePick} from './src/selection.js';
import {loadDraft,saveDraft} from './src/draft.js';
import {CLASS_NAMES,CLASS_KEYS,$,renderPicks,setSystemMessage,createSampleCard,updateQuest,setupMobileVoteLink} from './src/arena-view.js';

const ids=DEMO_SAMPLES.map(s=>s.id);
const byId=new Map(DEMO_SAMPLES.map(s=>[s.id,s]));
let storage=null;
try{storage=window.localStorage;}catch{/* Disable persistence if storage is unavailable. */}
const restored=loadDraft(storage,ids);
let selected=restored.picks,page=1;let savedReason=restored.reason;
const SIZE=window.innerWidth<=620?6:12;
$('reason-live').value=restored.reason;
$('mode-badge').className='mode-tag demo-mode';
updateQuest([3,5],'DEMO / 01');
$('metric-loss').textContent='0.820';
$('metric-accuracy').textContent='61.4%';
$('metric-round').textContent='DEMO';
setSystemMessage('DEMO / 数値・予測・画像は模擬データです。推薦はこのブラウザにのみ保存され、実際のAIは学習しません。','warning');
$('pool-caption').textContent='30件の模擬データ';
$('dataset-rights').textContent='ⓘ 模擬データを使用しています。実際のCIFAR-10画像や予測結果ではありません。';
$('refresh').textContent='↻ 検索条件をリセット';
$('save-reason').textContent='推薦理由のメモを保存 ↗';
$('round-phase').textContent='DEMO：画像選択はこのブラウザに自動保存されます。';
for(let i=0;i<10;i++){
  const option=document.createElement('option');option.value=CLASS_KEYS[i];option.textContent=CLASS_NAMES[i];$('label-filter').append(option);
}
function note(message,level='info'){$('vote-status').textContent=message;$('vote-status').dataset.level=level;}
function drawPicks(){renderPicks(selected,{onRemove:id=>updatePick(id,false),getLabel:id=>byId.get(id)?.className||''});}
function results(){
  const root=$('results');root.replaceChildren();
  const panel=document.createElement('div');panel.className='results-pending';
  const icon=document.createElement('span');icon.className='pending-symbol';icon.setAttribute('aria-hidden','true');icon.textContent='◌';
  const title=document.createElement('h3');title.textContent='デモでは学習を実行しません';
  const subtitle=document.createElement('p');subtitle.textContent='本番ではここに、投票モデルとランダム学習モデルの実測Lossを表示します。';
  panel.append(icon,title,subtitle);root.append(panel);
}
function render(){
  drawPicks();
  const data=filterSamples(DEMO_SAMPLES,{
    query:$('query').value,classKey:$('label-filter').value||'all',
    wrongOnly:$('wrong-only-live').checked,sort:'loss'
  });
  const maxPage=Math.max(1,Math.ceil(data.length/SIZE));
  page=Math.min(page,maxPage);
  const start=(page-1)*SIZE;const visible=data.slice(start,start+SIZE);
  $('sample-grid').replaceChildren(...visible.map(s=>{
    const label=CLASS_KEYS.indexOf(s.classKey);
    return createSampleCard({id:s.id,label,prediction:{predicted:CLASS_NAMES.indexOf(s.predictedClass),loss:s.loss},selected:selected.includes(s.id),disabled:!selected.includes(s.id)&&selected.length>=10,votes:0,onToggle:updatePick,demo:true});
  }));
  $('page-caption').textContent=`${data.length}件中 ${visible.length?start+1:0}–${start+visible.length}件を表示 · DEMO`;
  $('empty-state').hidden=data.length>0;
  $('empty-heading').textContent='一致するデータがありません';
  $('empty-description').textContent='検索条件を変更してください。';
  $('empty-action').textContent='検索条件をクリア';
  $('prev-page').disabled=page<=1;$('prev-page-bottom').disabled=page<=1;
  $('next-page').disabled=page>=maxPage;$('next-page-bottom').disabled=page>=maxPage;
  $('bottom-page-label').textContent=`ページ ${page} / ${maxPage}`;
}
function updatePick(id,add){
  if(!ids.includes(id)){note('この画像IDはデモに存在しません。');return;}
  try{
    selected=add?addPick(selected,id):togglePick(selected,id);
    const ok=saveDraft(storage,selected,savedReason);
    note(ok?'選択をこのブラウザに保存しました。実際の投票・学習には反映されません。':'選択を変更しました。保存が使えないため画面内だけに保持します。',ok?'success':'warning');render();
    document.querySelector(`[data-pick-id="${id}"]`)?.focus({preventScroll:true});
  }catch(e){note(e.message);}
}
$('filters').addEventListener('submit',e=>{e.preventDefault();page=1;render();});
$('query').addEventListener('input',()=>{page=1;render();});
$('label-filter').addEventListener('change',()=>{page=1;render();});
$('wrong-only-live').addEventListener('change',()=>{page=1;render();});
$('prev-page').addEventListener('click',()=>{page--;render();});
$('next-page').addEventListener('click',()=>{page++;render();});
$('prev-page-bottom').addEventListener('click',()=>{if(page>1){page--;render();$('explore').scrollIntoView({block:'start'});}});
$('next-page-bottom').addEventListener('click',()=>{page++;render();$('explore').scrollIntoView({block:'start'});});
$('id-form-live').addEventListener('submit',e=>{e.preventDefault();const v=$('sample-id').value.trim();if(v)updatePick(Number(v),true);$('sample-id').value='';});
$('reason-live').addEventListener('input',()=>{$('note-state').textContent='未保存のメモがあります。';});
$('save-reason').addEventListener('click',()=>{
  const text=$('reason-live').value;const ok=saveDraft(storage,selected,text);
  if(ok){savedReason=text;$('note-state').textContent='メモを保存しました。';}
  note(ok?'推薦理由のメモをこのブラウザに保存しました。実際の投票・学習には反映されません。':'ブラウザ保存が許可されていません。入力内容は画面内に残ります。',ok?'success':'error');
});
$('empty-action').addEventListener('click',()=>{
  $('query').value='';$('label-filter').value='';$('wrong-only-live').checked=false;page=1;render();
});
$('refresh').addEventListener('click',()=>{
  $('query').value='';$('label-filter').value='';$('wrong-only-live').checked=false;page=1;render();note('検索条件を初期化しました。');
});
render();results();setupMobileVoteLink();
