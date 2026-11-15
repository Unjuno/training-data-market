/** UI-only view models: do not invent game measurements or outcome. */
import {CLASS_NAMES} from './arena-view.js';

export function questIntel(metrics,targets){
  if(!Array.isArray(targets)||targets.length!==2||!targets.every(x=>Number.isInteger(x)&&x>=0&&x<10))return [];
  return targets.map(id=>{
    const value=metrics?.recall?.length===10?metrics.recall[id]:null;
    return {label:CLASS_NAMES[id],recall:Number.isFinite(value)&&value>=0&&value<=1?`${(value*100).toFixed(1)}%`:'—'};
  });
}
export function progressState(count,hasForecast,canVote){
  return {next:!canVote?'投票受付終了・実験結果を確認':
    count===0?'画像を1枚選ぶ':!hasForecast?'次は結果を予測する':'締切後の学習結果を待つ',
    selected:count>0,forecasted:!!hasForecast};
}
export function scoreSummary(record){
  if(!record||!record.scored_rounds)return 'まだ採点された予測はありません';
  return `累計 ${Number(record.total_points).toLocaleString('ja-JP')} pt / ${record.scored_rounds} ラウンド採点`;
}
export function forecastHint(percent){
  if(percent===50)return '50%：五分五分の予測（基準点は75 pt）';
  return `${percent}%：CommunityがRandomより対象Lossを下げると予測`;
}

/** An actionable destination for the player, derived only from saved state. */
export function nextAction({count=0,hasForecast=false,canVote=false,hasResults=false}={}){
  if(!canVote)return hasResults?
    {href:'#results-section',label:'直近の結果を見る',description:'投票受付が終わりました。前回の学習結果を確認できます。'}:
    {href:'#batch-rail',label:'バッチ処理の状況を見る',description:'締切後は投票を変更できません。'};
  if(count===0)return {href:'#explore',label:'画像を選ぶ',description:'気になる画像をまず1枚推薦してください。'};
  if(!hasForecast)return {href:'#prediction-section',label:'勝敗を予測する',description:'次はCommunityとRandomの勝敗を予測しましょう。'};
  return hasResults?
    {href:'#results-section',label:'前回の実験を見る',description:'今回の推薦と予測は保存済み。前回の結果を見て次の戦略を考えましょう。'}:
    {href:'#batch-rail',label:'締切時刻を確認する',description:'今回の推薦と予測は保存済みです。結果発表までお待ちください。'};
}

/** Do not imply a single image caused a model accuracy improvement. */
export function participationMessage(summary){
  if(!summary)return null;
  if(!summary.recommended_count)return 'このラウンドは画像を推薦していません。';
  if(!Number.isInteger(summary.adopted_count))return '当時の投票枠の採用記録がありません。';
  return `あなたの推薦 ${summary.recommended_count}枚中${summary.adopted_count}枚が投票枠から学習バッチに採用されました。`;
}

/** A previous round's result must not fill the current round's step 04. */
export function isCurrentRoundRevealed(current, publishedRoundId){
  return Boolean(current?.status==='PUBLISHED' && current.id===publishedRoundId);
}

/** Winning the forecast and promoting a model are separate decisions. */
export function promotionMessage(promotion){
  if(promotion==='community')return 'Communityモデルが共有AIに採用されました。';
  if(promotion==='random')return 'Community側でも学習しましたが、共有AIにはRandomモデルが採用されました。';
  return '学習実験は行われましたが、共有AIの更新は見送られました。';
}
