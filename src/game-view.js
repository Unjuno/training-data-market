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
