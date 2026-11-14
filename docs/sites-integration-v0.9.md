# Sites連携・投票締切・公開前条件（v0.9）

## 1. 結論

Sitesの画面だけでは学習ワーカーは動きません。FastAPIとPyTorchワーカーを**独立したCPU/GPUホスト**で起動し、永続ストレージを共有します。Sites自体の作成・公開はChatGPT Workで操作します。本リポジトリをpushしてもSitesが自動デプロイされるわけではありません。

## 2. ローカルの本物のゲームを動かす

推奨: Python 3.11+、torch 2.10.0 CPU、torchvision 0.25.0、Node.js 22。

```bash
python -m pip install -r requirements-ml.txt -r requirements-test.txt
python -m backend.local_demo --port 8000 --round-seconds 90
# ブラウザで http://127.0.0.1:8000 を開く
```

公式CIFAR-10は不要です。このモードは自作の合成ピクセルアートを使い、実PyTorchで両アーム40ステップずつ学習します。**自然画像を学習しているという主張はできません。** ローカルデモは127.0.0.1に限定されます。

## 3. 分離する責務

```text
Sites UI + trusted user authentication
         ↓ same-origin proxy or verified server-side gateway
Private HTTPS API (FastAPI; no browser-admin tokens)
         ↓ transactional SQLite for single-host pilot
Worker queue / operator schedule
         ↓
PyTorch worker + private dataset/validation/checkpoints
```

Sites側で同一オリジンのリバースプロキシが利用できるか事前検証してください。提供されなければ、APIホストでUIを配信する構成を選びます。ワイルドカードCORSやCookieの`SameSite=None`だけで認証を回避してはいけません。Sitesのログインユーザーと匿名ブラウザCookieは同一ではありません。正式公開前に、SitesのユーザーIDを信頼できるサーバー側認証フローで検証し、推薦の登録・閲覧に結びつける必要があります。

## 4. 締切とラウンド状態

- `rounds.closes_at`はSQLiteに保存するUTC Unix秒。データベースの`OPEN`表示が残っていても、サーバー時刻が締切以降なら推薦・取消・メモ編集を**409で拒否**します。
- API `GET /v1/rounds/current`は`server_time`、`opened_at`、`closes_at`を返します。UIはサーバー時刻差を補正したカウントダウンを表示し、毎15秒で結果を自動更新します。
- ワーカーは`closes_at`を基準に締切を確定。次ラウンドへ予定の投票期間を引き継ぎます。既存v0.8 SQLiteは初回起動時にカラムを追加し、未設定の締切へ`opened_at + TDM_ROUND_SECONDS`（既定86400秒）を適用します。
- ロールバックでも過去の評価値を上書きしないため、`metrics/round-XXXX.json` / `predictions/round-XXXX.json`でラウンド固有の評価結果を保存します。旧チェックポイント名のファイルは読み取りフォールバックとして残します。

## 5. 安全な公開権利ゲート

- 自作合成画像は `TDM_DEMO_MODE=true` のローカルデモだけで公開可能。
- CIFAR-10画像は**両方**満たすまで配信しない: `manifest.json` の `image_rights_status: "APPROVED"` と `TDM_PUBLISH_IMAGES=true`。これは運営側による使用権利確認の記録であり、技術的フラグが合法性を保証するわけではありません。
- `manifest`, checkpoint, safety split, admin token, `.env`はWeb公開しない。

## 6. Composeは非公開ステージング専用

`.env.example`をコピーしランダムな64桁以上の独立キーを設定。`mkdir -p state data`してから起動します（ホストボリュームの書込権限を確認）。

```bash
cp .env.example .env
# TDM_COOKIE_SECRET / TDM_ADMIN_KEY に自分で生成した秘密値を記入
# 自作合成デモで検証する場合は TDM_DEMO_MODE=true にする
mkdir -p state data
docker compose build
docker compose run --rm worker python -m backend.ml demo-prepare --state-root /state
docker compose up -d
```

HTTPのローカルポートにのみバインドし、**この構成だけで公開運用してはいけません**。GitHub Actionsは`npm run check/build`とPython回帰テストを自動実施する設定です。初回のCIとDockerビルドが実際に通過するまで、本番対応とは判定しません。

## 7. 公開前ブロッカー

- 本人確認・Bot対策・投票レート制限・Sitesとの認証連携
- 信頼できるTLS環境と秘密鍵の運用、API/workerの監視・再起動・バックアップ
- CIFAR-10の公開権利確認、実データでの性能計測
- 公開URL上のPC/モバイルE2Eとユーザーテスト
