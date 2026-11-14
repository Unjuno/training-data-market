import {DEMO_SAMPLES,CLASS_OPTIONS} from "./src/demo-data.js";
import {filterSamples,togglePick,addPick} from "./src/selection.js";
import {loadDraft,saveDraft} from "./src/draft.js";

const $=id=>document.getElementById(id);
const validIds=DEMO_SAMPLES.map(s=>s.id);
let storage=null;
try { storage=window.localStorage; } catch { /* Memory-only mode. */ }
const restored=loadDraft(storage,validIds);
let picks=restored.picks;
$("reason").value=restored.reason;

for(const cls of CLASS_OPTIONS){
  const option=document.createElement("option");
  option.value=cls.key; option.textContent=cls.label;
  $("class-filter").append(option);
}

function say(message){$("status").textContent=message;}
function save(){return saveDraft(storage,picks,$("reason").value);}
function pick(id,addOnly=false){
  if(!validIds.includes(Number(id))){say("そのIDのデモ画像は存在しません。");return;}
  try {
    picks=(addOnly?addPick:togglePick)(picks,id);
    say("選択を変更しました。保存するには「推薦をローカル保存」を押してください。");
    render();
  } catch(err){say(err.message);}
}

function makeCard(sample){
  const card=document.createElement("article");
  card.className="sample-card"+(picks.includes(sample.id)?" is-selected":"");
  const art=document.createElement("div");art.className="sample-art "+sample.classKey;art.textContent=sample.emoji;
  art.setAttribute("role","img");art.setAttribute("aria-label",sample.className+"の代替絵文字（実画像ではありません）");
  const top=document.createElement("div");top.className="sample-top";
  const id=document.createElement("span");id.className="sample-id";id.textContent=`#${sample.id}`;
  const tag=document.createElement("span");tag.className=sample.correct?"ok-tag":"error-tag";tag.textContent=sample.correct?"正解":"誤分類";
  top.append(id,tag);
  const name=document.createElement("h3");name.className="sample-label";name.textContent=sample.className;
  const pred=document.createElement("p");pred.className="sample-pred";pred.textContent=`AIの予測：${sample.predictedClass}`;
  const bottom=document.createElement("div");bottom.className="sample-bottom";
  const loss=document.createElement("span");loss.textContent=`Loss `;const num=document.createElement("strong");num.textContent=sample.loss.toFixed(2);loss.appendChild(num);
  const btn=document.createElement("button");btn.type="button";btn.className="select-button";btn.dataset.pickId=String(sample.id);
  const active=picks.includes(sample.id);btn.textContent=active?"選択済み ✓":"推薦する";btn.setAttribute("aria-pressed",String(active));
  btn.setAttribute("aria-label",`画像${sample.id} ${sample.className}を${active?"推薦解除":"推薦"}`);
  btn.addEventListener("click",()=>pick(sample.id));
  bottom.append(loss,btn);card.append(art,top,name,pred,bottom);return card;
}
function render(){
  const active=document.activeElement;
  const focusPick=active?.dataset?.pickId;
  const focusRemove=active?.dataset?.removeId;
  const data=filterSamples(DEMO_SAMPLES,{
    query:$("search").value,classKey:$("class-filter").value,
    wrongOnly:$("wrong-only").checked,sort:$("sort").value
  });
  const grid=$("sample-grid");grid.replaceChildren(...data.map(makeCard));
  $("result-count").textContent=`${data.length}件を表示 / ${DEMO_SAMPLES.length}件`;
  $("empty-message").hidden=data.length>0;
  $("pick-count").textContent=`${picks.length} / 10`;
  const list=$("pick-list");list.replaceChildren();
  if(!picks.length){const li=document.createElement("li");li.className="muted";li.textContent="まだ選択されていません。";list.append(li);}
  for(const id of picks){
    const sample=DEMO_SAMPLES.find(s=>s.id===id);
    const li=document.createElement("li");li.className="pick-chip";
    li.append(document.createTextNode(`#${id} ${sample.className}`));
    const remove=document.createElement("button");remove.type="button";remove.textContent="×";remove.dataset.removeId=String(id);
    remove.setAttribute("aria-label",`画像${id}を解除`);remove.addEventListener("click",()=>pick(id));
    li.append(remove);list.append(li);
  }
  // Empty selection must be saveable, otherwise previously saved picks reappear.
  $("save-picks").disabled=false;
  $("clear-picks").disabled=picks.length===0;
  if(focusPick) document.querySelector(`[data-pick-id="${focusPick}"]`)?.focus({preventScroll:true});
  if(focusRemove) {
    const next=document.querySelector(`[data-remove-id="${focusRemove}"]`) || $("save-picks");
    next.focus({preventScroll:true});
  }
}

$("filter-form").addEventListener("submit",ev=>ev.preventDefault());
["search","class-filter","sort","wrong-only"].forEach(id=>{
  $(id).addEventListener(id==="search"?"input":"change",render);
});
$("id-form").addEventListener("submit",ev=>{
  ev.preventDefault();pick($("id-input").value,true);$("id-input").value="";
});
$("save-picks").addEventListener("click",()=>{
  say(save()?`推薦${picks.length}枚と理由をブラウザに保存しました（サーバーへの送信・AIの学習は行いません）。`:
    "ブラウザへの保存が許可されていません。選択内容はこの画面内で保持されます。");
});
$("clear-picks").addEventListener("click",()=>{picks=[];say("選択を解除しました。保存するには「推薦をローカル保存」を押してください。");render();});
render();
