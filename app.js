import {DEMO_SAMPLES} from './src/demo-data.js';
import {filterSamples,addPick,togglePick} from './src/selection.js';
import {loadDraft,saveDraft} from './src/draft.js';
import {CLASS_NAMES,CLASS_KEYS,$,renderPicks,setSystemMessage,createSampleCard,updateQuest,setupMobileVoteLink} from './src/arena-view.js';

const ids=DEMO_SAMPLES.map(s=>s.id);
const byId=new Map(DEMO_SAMPLES.map(s=>[s.id,s]));
let storage=null;
try{storage=window.localStorage;}catch{/* Disable persistence if storage is unavailable. */}
const restored=loadDraft(storage,ids);
let selected=restored.picks,page=1;
const SIZE=12;
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
$('save-reason').textContent='デモの推薦を保存 ↗';
for(let i=0;i<10;i++){
  const option=document.createElement('option');option.value=CLASS_KEYS[i];option.textContent=CLASS_NAMES[i];$('label-filter').append(option);
}
function note(message){$('vote-status').textContent=message;}
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
  $('prev-page').disabled=page<=1;
  $('next-page').disabled=page>=maxPage;
}
function updatePick(id,add){
  if(!ids.includes(id)){note('この画像IDはデモに存在しません。');return;}
  try{
    selected=add?addPick(selected,id):togglePick(selected,id);
    note('選択を変更しました。「デモの推薦を保存」でブラウザへ記録できます。');render();
    document.querySelector(`[data-pick-id="${id}"]`)?.focus({preventScroll:true});
  }catch(e){note(e.message);}
}
$('filters').addEventListener('submit',e=>{e.preventDefault();page=1;render();});
$('query').addEventListener('input',()=>{page=1;render();});
$('label-filter').addEventListener('change',()=>{page=1;render();});
$('wrong-only-live').addEventListener('change',()=>{page=1;render();});
$('prev-page').addEventListener('click',()=>{page--;render();});
$('next-page').addEventListener('click',()=>{page++;render();});
$('id-form-live').addEventListener('submit',e=>{e.preventDefault();const v=$('sample-id').value.trim();if(v)updatePick(Number(v),true);$('sample-id').value='';});
$('save-reason').addEventListener('click',()=>{
  const ok=saveDraft(storage,selected,$('reason-live').value);
  note(ok?`ブラウザに${selected.length}件の選択と理由を保存しました。実際のAI学習・サーバー投票には反映されません。`:'ブラウザ保存が許可されていません。画面内の選択は維持されます。');
});
$('refresh').addEventListener('click',()=>{
  $('query').value='';$('label-filter').value='';$('wrong-only-live').checked=false;page=1;render();note('検索条件を初期化しました。');
});
render();results();setupMobileVoteLink();
