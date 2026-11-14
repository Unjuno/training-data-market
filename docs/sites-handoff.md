# ChatGPT Sites 実装・ホスティング引き継ぎ（2026-11-15）

## 何があるか

GitHubには日本語ライブ画面（`live.html`, `live.js`, `live.css`）、共有投票API（`backend/service.py`）、SQLite DB（`backend/store.py`）、Python/PyTorch学習ワーカー（`backend/ml.py`, `backend/worker.py`）とテストが収録される。旧静的デモは`index.html`。Local APIのトップ`/`はライブ画面を返す。

## Sitesで満たす条件

1. `@Sites` で既存デザインを非公開プレビューに再現する。
2. Sitesの利用可能なサーバー・DB・認証の仕様を確認し、共有ユーザーの推薦を永続化する。匿名cookieは技術パイロットであり、正式認証の代用品ではない。
3. 学習は外部CPU/GPUサーバー上のPythonワーカーに委譲する。SitesがPyTorchやバックグラウンド学習を直接実行できるとは仮定しない。Sites内DBと外部ワーカーの間で、認証済みジョブ/結果契約を設計・実装する。
4. ローカルAPIと互換性があることを確認。実運用で API の /v1 が別ホストの場合は、資格情報を保護する同一オリジンProxyなどを使用し、CORSの無制限許可・ブラウザへの管理者鍵送出をしない。
5. CIFAR-10画像の公開許可が明確でない場合は画像の配信を無効にする。データセットやモデル重みをGitHubに含めない。
6. 画面の実測指標は`metrics/<checkpoint>.json`のみから取得し、欠損時に架空の数値を表示しない。
7. 失敗・ロールバックを実際の結果として表示し、Community勝敗とPromotion判断を分離する。

## ローカルAPI契約

| Method | Path | 挙動 |
|---|---|---|
| GET | `/health` | サーバー準備状態 |
| GET | `/v1/rounds/current` | 現行Round・検証指標。未初期化なら明示 |
| GET | `/v1/samples` | page, limit<=48, label, query, wrong_only |
| GET | `/v1/samples/{id}` | ID・正解・推論・Loss（利用可能なら） |
| GET | `/v1/samples/{id}/image` | 権利承認時のみ候補PNG |
| GET | `/v1/rounds/{id}/picks/me` | 自分の推薦IDと理由 |
| PUT/DELETE | `/v1/rounds/{id}/picks/{sample_id}` | 最大10件・締切制御・重複防止 |
| PUT | `/v1/rounds/{id}/note` | 推薦理由の保存、400字以内 |
| GET | `/v1/rounds/history` | 最近日付順ラウンド |
| GET | `/v1/rounds/{id}/results` | 実験結果・安全判定 |
| POST | `/v1/admin/rounds/{id}/lock` | 管理者キー必須、受理後ワーカー側で実行 |

`run_locked_round`はローカルの閉鎖済みラウンドを実学習し、結果保存と次ラウンド作成を行う。公開APIのHTTP要求で直接GPUを起動しない。

## 不足する外部資源

- Sitesのサイト作成・非公開プレビュー・公開URL（本チャットからは操作できない）
- CIFAR-10データセット本体（この実行環境では未取得）と公開権利の確認
- 運営者が確保するCPU/GPUバックエンド、永続DB/モデル保存とジョブスケジューラ
- 公開用の本人確認済み認証と不正投票対策
- ラウンドを跨ぐ負荷・障害試験、実データでの回帰試験

## 完了条件

画面が表示されるだけではなく、**実データ探索→認証済み推薦→締切→2アーム学習→評価→採否→次ラウンド**が同一共有環境で完走し、AC-01〜18を実測PASSにできた時にのみMVP完成とする。
