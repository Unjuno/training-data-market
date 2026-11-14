/** Shared UI presentation for synthetic demo and real same-origin API mode.
 * Display-only fallback art is deliberately NOT portrayed as a CIFAR photograph.
 */
export const CLASS_NAMES=['飛行機','自動車','鳥','猫','鹿','犬','カエル','馬','船','トラック'];
export const CLASS_KEYS=['airplane','automobile','bird','cat','deer','dog','frog','horse','ship','truck'];
const GLYPHS=['AIR','CAR','BRD','CAT','DER','DOG','FRG','HRS','SHP','TRK'];
export const $=id=>document.getElementById(id);
export function element(parent,tag,value,cssClass){const el=document.createElement(tag);el.textContent=String(value);if(cssClass)el.className=cssClass;parent.append(el);return el;}
export function updateQuest(targets,roundLabel){
  const valid=Array.isArray(targets)&&targets.length===2&&targets.every(Number.isInteger);
  $('target-pair').textContent=valid?targets.map(i=>CLASS_NAMES[i]).join(' × '):'弱点を解析中';
  $('quest-visual-a').textContent=valid?GLYPHS[targets[0]]:'?';
  $('quest-visual-b').textContent=valid?GLYPHS[targets[1]]:'?';
  $('quest-name-a').textContent=valid?CLASS_KEYS[targets[0]].toUpperCase():'UNKNOWN';
  $('quest-name-b').textContent=valid?CLASS_KEYS[targets[1]].toUpperCase():'UNKNOWN';
  $('quest-round').textContent=roundLabel||'ROUND —';
}
export function updatePickMeter(count){
  $('my-count').textContent=`${count} / 10`;
  $('mobile-pick-count').textContent=`${count} / 10`;
  $('pick-meter-fill').style.width=`${Math.max(0,Math.min(count,10))*10}%`;
}
export function createSampleCard({id,label,prediction=null,votes=0,image_url=null,selected=false,disabled=false,onToggle,demo=false}){
  const card=document.createElement('article');card.className='sample-card'+(selected?' is-selected':'');
  const art=element(card,'div','','sample-art art-'+label);
  element(art,'span',`DATA / ${String(label).padStart(2,'0')}`,'art-code');
  element(art,'span',GLYPHS[label]||'IMG','art-glyph');
  element(art,'span',demo?'模擬表示': '画像非公開','art-caption');
  if(image_url && !demo){
    // URLs come from the same-origin backend, not from user-submitted content.
    const url=new URL(image_url,window.location.origin);
    if(url.origin===window.location.origin && url.pathname.startsWith('/v1/samples/')){
      const img=document.createElement('img');img.src=url.pathname;img.alt=`学習候補 #${id}、正解クラス：${CLASS_NAMES[label]}`;img.loading='lazy';img.width=160;img.height=160;
      img.addEventListener('load',()=>{art.querySelector('.art-caption').textContent='CIFAR-10';});
      img.addEventListener('error',()=>{img.remove();art.querySelector('.art-caption').textContent='画像を取得できません';});
      art.append(img);
    }
  }
  const body=element(card,'div','','sample-card-content');
  const top=element(body,'div','','sample-top');element(top,'span',`#${id}`,'sample-id');
  const validPrediction=prediction&&Number.isInteger(prediction.predicted);
  const wrong=validPrediction&&prediction.predicted!==label;
  element(top,'span',validPrediction?(wrong?'誤分類':'正解'):'未推論',wrong?'error-tag':'ok-tag');
  element(body,'h3',CLASS_NAMES[label]||'不明','sample-label');
  element(body,'p',validPrediction?`AIの予測：${CLASS_NAMES[prediction.predicted]}`:'AIの予測：未計測','sample-pred');
  const bottom=element(body,'div','','sample-bottom');
  const loss=element(bottom,'span','', 'sample-loss');element(loss,'small','SAMPLE LOSS');
  element(loss,'span',Number.isFinite(prediction?.loss)?prediction.loss.toFixed(3):'—');
  element(bottom,'span',`${votes} 票`,'sample-votes');
  const btn=element(body,'button',selected?'✓ 推薦済み・解除する':'+ この画像を推薦する','select-button');
  btn.type='button';btn.dataset.pickId=String(id);btn.disabled=disabled;
  btn.setAttribute('aria-pressed',String(selected));btn.setAttribute('aria-label',`画像${id}、${CLASS_NAMES[label]}を${selected?'推薦解除':'推薦'}`);
  btn.addEventListener('click',()=>onToggle(id,!selected));
  return card;
}
export function renderPicks(ids,{disabled=false,onRemove,getLabel=()=>''}={}){
  const list=$('my-picks');list.replaceChildren();updatePickMeter(ids.length);
  if(!ids.length){element(list,'li','まだ推薦がありません。気になるデータを探してください。','pick-empty');return;}
  for(const id of ids){
    const item=element(list,'li','','pick-chip');
    element(item,'span',`#${id}${getLabel(id)?' · '+getLabel(id):''}`);
    const btn=element(item,'button','×');btn.type='button';btn.disabled=disabled;btn.dataset.removeId=String(id);
    btn.setAttribute('aria-label',`画像${id}を推薦から解除する`);
    btn.addEventListener('click',()=>onRemove(id));
  }
}
export function setSystemMessage(message,level='info'){
  $('app-alert-text').textContent=message;$('app-alert').dataset.level=level;
}
export function setMetric(value,elId,format){
  $(elId).textContent=Number.isFinite(value)?format(value):'—';
}
export function renderResults(data){
  const node=$('results');node.replaceChildren();
  if(!data){
    const panel=element(node,'div','','results-pending');element(panel,'span','◌','pending-symbol');
    element(panel,'h3','学習結果を待っています');element(panel,'p','ラウンド終了後に、同じ初期モデルから学習した二つのモデルの実測値を表示します。');return;
  }
  const box=element(node,'div','','result-data');
  element(box,'div',`${data.round_id} / ${data.target_pair.map(i=>CLASS_NAMES[i]).join(' × ')}`,'result-kicker');
  element(box,'h3','Community と Random の実測比較');
  const table=element(box,'table','','result-table');
  const head=element(table,'thead','');const headRow=element(head,'tr','');
  for(const h of ['指標','学習前','投票モデル','ランダム'])element(headRow,'th',h);
  const body=element(table,'tbody','');
  for(const row of [
    ['対象ペアのLoss',data.before.target_loss,data.community.target_loss,data.random.target_loss],
    ['改善量',null,data.before.target_loss-data.community.target_loss,data.before.target_loss-data.random.target_loss]
  ]){
    const tr=element(body,'tr','');row.forEach((v,i)=>element(tr,'td',i===0?v:v===null?'—':Number(v).toFixed(4)));
  }
  const verdict=element(box,'div','','result-verdict');element(verdict,'span','共有AIへの反映');
  element(verdict,'strong',data.promotion==='community'?'投票モデルを採用':data.promotion==='random'?'ランダムモデルを採用':'更新せず（ロールバック）');
  element(box,'p',`投票由来 ${data.voted_count} 枚 / 合計 128 枚・各アーム 40 更新ステップ`,'result-meta');
}

/** Floating mobile shortcut is shown only after the hero is out of view. */
export function setupMobileVoteLink(){
  const link=document.querySelector('.mobile-vote-link');if(!link)return;
  const update=()=>{
    const ballot=$('vote-panel').getBoundingClientRect();
    const ballotInView=ballot.top<innerHeight-90 && ballot.bottom>80;
    link.classList.toggle('is-visible',window.scrollY>460&&!ballotInView);
  };
  window.addEventListener('scroll',update,{passive:true});window.addEventListener('resize',update,{passive:true});update();
}
