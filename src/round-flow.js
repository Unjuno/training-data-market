/** Read-only view model for server-authoritative timed-batch phases. */
export function batchPhase(round, nowMs) {
  const unavailable = { id:'uninitialized', title:'学習データを準備中', description:'準備が完了すると最初の投票を開始します。', canVote:false };
  if(!round)return unavailable;
  const isOpen=round.status==='OPEN' && Number.isFinite(Number(round.closes_at)) &&
    Number(round.closes_at)>nowMs/1000;
  if(isOpen)return {id:'voting',title:'投票受付中',description:'締切まで画像を推薦・変更できます。学習はまだ始まりません。',canVote:true};
  if(round.status==='OPEN')return {id:'awaiting-lock',title:'投票締切・バッチ待機',description:'受付は終了しました。サーバーが確定処理を行うまでお待ちください。',canVote:false};
  if(round.status==='LOCKED')return {id:'locked',title:'投票確定・バッチ準備中',description:'投票は凍結され、学習対象の画像を確定しています。',canVote:false};
  if(round.status==='TRAINING')return {id:'training',title:'バッチ学習中',description:'CommunityとRandomを同じ初期状態から追加学習しています。完了後に結果が公開されます。',canVote:false};
  if(round.status==='PUBLISHED')return {id:'published',title:'結果公開済み',description:'実測の勝敗と共有AIへの採用結果を確認してください。',canVote:false};
  return {id:'unavailable',title:'処理状態を確認中',description:'状態を取得できません。情報を更新してください。',canVote:false};
}
