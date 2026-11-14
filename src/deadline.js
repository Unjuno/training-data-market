/**
 * Pure view-model for the authoritative round deadline.
 * closes_at is a UNIX timestamp in seconds; nowMs is milliseconds corrected
 * using the server_time field. A missing deadline fails closed.
 */
export function deadlineState(round, nowMs) {
  if (!round) return {isOpen:false,remainingSeconds:0,label:'ラウンド準備中'};
  if (round.status !== 'OPEN') return {isOpen:false,remainingSeconds:0,label:'推薦受付は終了しました'};
  const due=Number(round.closes_at);
  if (!Number.isFinite(due) || due<=0 || !Number.isFinite(nowMs)) {
    return {isOpen:false,remainingSeconds:0,label:'締切時刻を確認できません。推薦を停止しています'};
  }
  const remainingSeconds=Math.max(0,Math.ceil(due-nowMs/1000));
  if (remainingSeconds===0) return {isOpen:false,remainingSeconds:0,label:'締切時刻で推薦受付終了。集計処理を待っています'};
  const hours=Math.floor(remainingSeconds/3600);
  const minutes=Math.floor((remainingSeconds%3600)/60);
  const seconds=remainingSeconds%60;
  const timeText=hours>0?`${hours}時間 ${minutes}分`:
                 minutes>0?`${minutes}分 ${seconds}秒`:`${seconds}秒`;
  return {isOpen:true,remainingSeconds,label:`締切まで ${timeText}`};
}
