# Training Data Market — CIFAR-10 Collaborative Training Game

ユーザーが共有AIの弱点を観察し、有効だと考える学習画像を推薦するゲーム。投票締切後、同一モデルから **Community/Randomの二分岐**で追加学習し、公開指標・採否・次のクエストを表示します。

**実装状態：ローカルAPI・投票・PyTorch学習コアを実装し、合成データでテスト済み。CIFAR-10本体は同梱しておらず、実データでの測定・Sites公開は未実施です。** 学習済みだと偽る表示をしていません。

## 重要：Sitesと学習ワーカーは別

ChatGPT Sitesには`@Sites`でサイトを作成できますが、PyTorch学習がSitesのランタイムで実行できるとは前提にしません。`live.html`と`live.js`をUI基盤とし、Sites内の認証・永続DBまたは認証済みの外部APIへ接続します。Python学習ワーカーは別ホストが必要です。具体的な引き継ぎは[SITES_PROMPT.md](SITES_PROMPT.md)と[docs/sites-handoff.md](docs/sites-handoff.md)を参照。

## リポジトリの構成

- `live.html` / `live.js` / `live.css`: 実測値のみを表示する日本語のライブ画面。画像公開が未承認ならプレースホルダーを表示。
- `backend/service.py`: FastAPI。共有投票の保存、検索ページング、状態・結果・履歴、管理者による締切。
- `backend/store.py`: SQLiteトランザクション。最大10票、重複排除、締切後の変更禁止、推薦理由の保存、結果の原子的公開。
- `backend/core.py`: クラス層化分割、投票上位最大64件、128枚の二分岐、弱点判定、安全ゲート。
- `backend/ml.py`: CIFAR-10ロード、軽量CNN、初期学習、各アーム40 optimizer steps、検証、Checkpoint昇格・ロールバック。
- `backend/worker.py`: 運営者が起動するラウンド実行スケジューラ。
- `index.html` / `app.js`: 既存の**架空データによる静的操作デモ**。`/demo.html`から確認。
- `docs/spec-v0.4.md`: 採用済み製品仕様と研究プロトコル。
- `tests_py/` / `tests/`: サーバー・モデル・ブラウザロジックの回帰テスト。

## ローカル実行手順（Python 3.11+、CPU）

1. 依存関係をインストール: `python -m pip install -r requirements-ml.txt -r requirements-test.txt`。
2. 使用許諾条件を自身で確認してからCIFAR-10公式データをローカルの`data/`に取得する。例： `python -c "from torchvision.datasets import CIFAR10; CIFAR10('data',train=True,download=True); CIFAR10('data',train=False,download=True)"`。データ本体をGitHubにコミットしない。
3. `python -m backend.ml prepare --data-root data --state-root state` で初期モデルを作成。50,000枚の公式訓練データを **2,000初期学習 / 3,000公開検証 / 2,000安全検証 / 43,000候補** に固定分割し、公式テスト10,000枚を隔離する。
4. 32文字以上のランダム値で環境変数`TDM_COOKIE_SECRET`、`TDM_ADMIN_KEY`を設定する（`.env.example`参照）。初期状態の `TDM_PUBLISH_IMAGES=false` は権利確認まで維持。
5. `uvicorn backend.service:app --host 127.0.0.1 --port 8000` を起動し、`http://127.0.0.1:8000`を開く。匿名ブラウザ識別を利用した**技術パイロット**であり、本人確認済みアカウントではない。
6. 24時間ごとの集計・追加学習には `python -m backend.worker --data-root data --state-root state` を別プロセスで実行（運営環境側で継続起動が必要）。即時検証は管理者が `POST /v1/admin/rounds/round-0001/lock` に `X-Admin-Key` を添えて締切後、 `python -m backend.ml train-round --data-root data --state-root state --round-id round-0001` を実行する。
7. 結果と次の弱点クエストはDBへ保存され、次のラウンドが自動生成される。学習実験中のアームは同じ重み・同じSGD momentum・同じseedで分岐する。

**注意**: `prepare`はCIFAR-10本体とCPU時間が必要です。ここではインターネットへのアクセスが制限されるため実データをダウンロード・学習できず、精度・実行速度は未測定です。

## テスト

```bash
node --check live.js
npm run check
npm run build
python -m pytest tests_py -q
```

## 安全性と公開時の制限

このローカルAPIは、署名付きの匿名ブラウザセッションで推薦を保存します。**公共サービスの本人確認や不正票防止は未実装**です。一般公開前にSitesで正規アカウント認証・不正対策・負荷制御を追加してください。

`TDM_PUBLISH_IMAGES`は権利確認済みのときだけ有効にすること。未承認の画像をPublicサイトに配布しない。管理者キー、Cookie秘密鍵、モデル重み、非公開検証セットをGitHub・クライアントJSへ入れない。最終テスト画像は学習・ユーザー探索に使わない。

実金・換金ベット、学習率の投票介入、EMA/Bollinger制御はMVPの対象外です。コードとデータセットの権利は別です。

## リンク

- [正式仕様 v0.4](docs/spec-v0.4.md)
- [実装状況・残件](docs/acceptance-status.md)
- [Sites引き継ぎ](docs/sites-handoff.md)
- [旧静的UIデモ](index.html)
