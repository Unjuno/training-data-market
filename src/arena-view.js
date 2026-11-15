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
export function createSampleCard({id,label,prediction=null,votes=0,image_url=null,image_kind='CIFAR-10',selected=false,disabled=false,onToggle,demo=false}){
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
      img.addEventListener('load',()=>{art.querySelector('.art-caption').textContent=image_kind==='SYNTHETIC_PIXEL_ART'?'合成ピクセルアート':'CIFAR-10';});
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
  const pair=Array.isArray(data.target_pair)?data.target_pair.map(i=>CLASS_NAMES[i]||'?').join(' × '):'評価対象';
  element(box,'div',`${data.round_id} / ${pair}`,'result-kicker');
  const verdict=data.forecast_verdict?.outcome;
  const headline=verdict==='community'?'Communityが勝利':verdict==='random'?'Randomが勝利':
    verdict==='tie'?'今回は引き分け':'今回は予測の採点対象外';
  const overview=element(box,'div','','result-overview');
  element(overview,'div','ROUND VERDICT','result-overline');
  element(overview,'h3',headline);
  element(overview,'p','対象2クラスの検証Lossが小さい方を勝者とします。個々の画像の効果を断定する結果ではありません。');
  const losses=[['Community',data.community?.target_loss],['Random',data.random?.target_loss]];
  const grid=element(box,'div','','result-scorecards');
  for(const [label,loss] of losses){
    const winner=(verdict==='community'&&label==='Community')||(verdict==='random'&&label==='Random');
    const card=element(grid,'div','',`result-scorecard${winner?' is-winner':''}`);
    element(card,'span',label.toUpperCase(),'result-card-label');
    element(card,'strong',Number.isFinite(loss)?Number(loss).toFixed(4):'—');
    element(card,'small',winner?'WINNER / LOWEST LOSS':'TARGET CROSS-ENTROPY');
  }
  const beforeLoss=data.before?.target_loss;
  const comLoss=data.community?.target_loss;
  const rndLoss=data.random?.target_loss;
  const asNumber=n=>Number.isFinite(n)?n.toFixed(4):'—';
  const comparison=element(box,'div','','result-experiment');
  element(comparison,'strong','対照実験の結果');
  const list=element(comparison,'dl','');
  for(const [title,value] of [
    ['学習前のLoss',asNumber(beforeLoss)],
    ['Communityの改善量',asNumber(beforeLoss-comLoss)],
    ['Randomの改善量',asNumber(beforeLoss-rndLoss)]]){
    const row=element(list,'div','','result-experiment-row');
    element(row,'dt',title);element(row,'dd',value);
  }
  const verdictBox=element(box,'div','','result-verdict');element(verdictBox,'span','共有AIへの反映（勝敗とは別判定）');
  element(verdictBox,'strong',data.promotion==='community'?'投票モデルを採用':data.promotion==='random'?'ランダムモデルを採用':'更新せず（ロールバック）');
  element(box,'p',`投票由来 ${data.voted_count??'—'} 枚 / 合計 128 枚・各アーム 40 更新ステップ`,'result-meta');
}

/** Floating mobile shortcut is shown only after the hero is out of view. */
export function setupMobileVoteLink(){
  const link=document.querySelector('.mobile-vote-link');if(!link)return;
  const update=()=>{
    const ballot=$('vote-panel').getBoundingClientRect();
    const ballotInView=ballot.top<innerHeight-90 && ballot.bottom>80;
    const readingResults=['results-section','how-it-works'].some(id=>{
      const r=$(id)?.getBoundingClientRect();
      return r && r.top<innerHeight-70 && r.bottom>70;
    });
    link.classList.toggle('is-visible',window.scrollY>460&&!ballotInView&&!readingResults);
  };
  window.addEventListener('scroll',update,{passive:true});window.addEventListener('resize',update,{passive:true});update();
}
