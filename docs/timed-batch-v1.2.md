# Training Data Market — 時間制バッチ運用仕様 v1.2

**適用範囲:** `backend/store.py`・`backend/worker.py`・`backend/ml.py`・`backend/service.py`・`live.js`。2026-11-15。

## 遊び方と運用契約

プレイヤーは共有AIの「現在の弱点ペア」を見て画像を最大10枚推薦し、CommunityアームがRandomアームより対象の検証Lossを下げる確率を予測する。**クリックした瞬間には学習しない**。投票は各ラウンドの保存済み `closes_at`（Unix epoch秒）まで有効で、サーバー時刻で厳密に判定する。後から到着した投票は、ワーカーが未稼働でもHTTP 409。

各ラウンド終了後、投票数の多い画像最大64件（同一クラスの上限あり）とランダム補完で128件のCommunityバッチを作る。Randomアームは同数・同更新予算のランダム抽出。2モデルは同一チェックポイント・オプティマイザ状態から各40更新し、検証Loss・安全ゲートで共有モデルへ反映するか判断する。結果と予測スコアを公開し、その後に次のラウンドを開く。

## サーバーが唯一の状態管理者

| 状態 | サーバーの操作 | プレイヤーに見せる情報 |
|---|---|---|
| `OPEN`（締切前） | 推薦・予測を保存 | 残り時間、締切の絶対時刻、ユニーク投票者数、推薦票数、予測件数 |
| `OPEN`（締切後） | 投票APIは拒否。ワーカーの処理待ち | `投票締切・バッチ待機`。投票を保存したと誤表示しない |
| `LOCKED` | 投票凍結。次に単一ワーカーが処理権取得 | `投票確定・バッチ準備中` |
| `TRAINING` | Community/Randomを追加学習・評価 | `バッチ学習中`。計測できない進捗率や終了予想時刻を作らない |
| `PUBLISHED` | 判定・採用理由・ポイントを公開 | `結果公開済み`。勝敗とモデルへの採用は別表示 |

**注:** `finalize_round` は `PUBLISHED` と次の `OPEN` を1 DBトランザクションで発行するため、通常は次ラウンドを見ながら前ラウンドの結果を閲覧する。上記の `PUBLISHED` は履歴上の状態でもある。

## Exactly-one-owner / recovery

- `GameStore.claim_round(round_id)` は SQLite の `BEGIN IMMEDIATE` 内で `LOCKED → TRAINING` を原子的に実施し、取得者だけにランダムな owner token を返す。2番目のワーカーは `None` を受け取り、そのラウンドを学習しない。
- 結果確定の `finalize_round(...,claim_token)` はステータスとトークンの両方が一致した場合のみ動く。古いワーカーや直接 `publish_result` する経路を拒否する。
- ワーカー異常終了時は **自動的に claim を失効させない**。CPU/GPUで旧プロセスが動いている可能性があり、時間経過だけで新ワーカーを動かすと二重学習になるため。
- 運営者が旧プロセス停止を確認した場合のみ `python -m backend.worker --state-root state --recover-round round-0001 --confirm-worker-stopped` で `TRAINING → LOCKED` に戻し、次回ポーリングが一度だけ処理を再開する。
- ロック取得競合は通常の409として扱い、ワーカー間の失敗と解釈しない。
- 再実行前の結果書き込み・アーティファクト整合性は運用担当者が確認する。単一DB上での最終確定はトークンで防御するが、外部でのGPU演算が**厳密に一回**という分散処理保証ではない。

## 実行方式

`python -m backend.worker --state-root state --data-root data --poll-interval 30` は**別プロセスで継続起動が必要**。WebリクエストやクリックからGPUを起動しない。`backend.local_demo` は合成画像・匿名クッキーのローカル実験専用で、公開サイトでは使わない。ChatGPT SitesはUIと認証、外部で永続DBとPython学習ワーカーを稼働させる設計とする。本番公開前に認証、公開権利、永続ストレージ、ホスト、ジョブ制御を別途確認する。

## API・UXの検証条件

- `GET /v1/rounds/current` は個人を特定できるIDを含まない `vote_summary` (`vote_count`,`voter_count`,`forecast_count`,`frozen`) と `closes_at` を返す。
- Liveページの `<link>` と `live.js` のすべてのES module importが **実FastAPIから200**で取得できること。ブラウザ内でソースを連結するだけのE2Eではこの問題を検知できない。
- 多重タイマー起動：2プロセスの同一ラウンド請求で成功者1つ、次ラウンド生成は1回。
- 受付境界：`now >= closes_at` で推薦・削除・予測更新・メモ更新すべて409。
- 合成画像の実学習：2アーム各40更新、同じ初期チェックポイント、結果公開、次ラウンド生成。
- 画面：390/820/1440pxの幅で横はみ出しなし。検索→推薦→予測→発表の操作をChromium上で検証。**実Google ChromeおよびSitesへのデプロイは別検証**。

## 現時点の制約

公式CIFAR-10実画像と公開権利、Google Chrome実機、ChatGPT Sitesでの実配備、ログインの一人一アカウント保証、第三者によるユーザビリティ検査は未完了。時間制ジョブの正確な時刻はコンテナの運用・スケジューラ稼働にも依存する。最初の公開前にこの制約をクリアする。
