# Training Data Market — CIFAR-10 Collaborative Training Game

ユーザーが共有AIの弱点を観察し、有効だと考える学習画像を推薦するゲーム。投票締切後、同一モデルから **Community/Randomの二分岐**で追加学習し、公開指標・採否・次のクエストを表示します。

**実装状態：ローカルAPI・投票・PyTorch学習コアを実装し、合成データでテスト済み。CIFAR-10本体は同梱しておらず、実データでの測定・Sites公開は未実施です。** 学習済みだと偽る表示をしていません。

## UX品質の改善（v0.7）

- 画像検索の300ms自動更新、各画面幅に応じた小さなページサイズ、一覧末尾からのページ移動。
- 推薦のサーバー保存を即時フィードバック。失敗時は画像IDと理由メモを維持し、エラーと検索結果0件を区別する。
- メモの保存状態と推薦の確定を分ける。キーボード操作の焦点を保持する。
- [UX品質仕様と未実施の人間テスト](docs/ux-quality-v0.7.md)。
- オプションのChromium実ブラウザ操作テスト: `python tests_e2e/ux_flow.py`（PlaywrightとChromiumが必要）。


## v1.1: Scout & Forecast — プレイ可能なゲームループ

- **観察**：共有モデルの公開検証Loss・クラス別Recall・現在の弱点ペアを確認します。評価値を予測値と混同しません。
- **推薦**：候補画像から最大10枚を選択。現在のクエストの2クラス、誤分類、全画像へのショートカットがあります。
- **予測**：CommunityがRandomより対象2クラスの検証Lossを下げる確率を5～95%（5%刻み）で提出。締切前なら編集可能です。
- **結果発表**：両モデルの実測値と勝敗、共有モデルへの採用・ロールバックを別々に表示します。プレイヤーの予測を0～100ポイントで採点し、このブラウザの履歴に記録します。

予測の採点は **`100 × [1 − (予測確率−結果)^2]` を整数丸め**（確率は0～1、Community勝利を1）。50%の予測は正解・不正解とも75ポイントです。投票ゼロ、同点（対象Loss差0.001以内）、無効測定は採点しません。ポイントはゲーム内の非換金値で、モデルの学習データ選択に影響しません。

`PUT /v1/rounds/{round_id}/forecast/me` は `{ "probability_pct": 75 }` のようなJSONを受け付けます。`GET /v1/rounds/{round_id}/forecast/me` は本人の保存済み予測、`GET /v1/game/me` は本人の累計予測スコアを返します。いずれも同一オリジンの署名付きブラウザセッションを使用し、本番認証ではありません。

スコアはグループの予測結果に対するものです。**個別画像・個人の選択が結果改善を引き起こしたという因果的な貢献度ではありません。**

- ゲーム設計: [v1.1のルールと判断基準](docs/design/2026-11-15-game-loop.md)
- 実装計画: [v1.1実装計画](docs/plans/2026-11-15-game-v1.1.md)
- ブラウザ検証: `PYTHONPATH=. python tests_e2e/game_smoke.py --port 8765 --state demo-state`（別端末でローカル実学習デモ起動後。Chromium144、about:blank経由の通信ブリッジによるテスト）

## 時間制バッチ v1.2

1ラウンドは **投票受付 → 締切確定 → 単一ワーカーによるバッチ学習 → 結果発表 → 次ラウンド**。クリックで学習は開始しません。`/v1/rounds/current` が個人情報を含まない投票集計値と締切時刻を返します。複数ワーカーの重複実行を claim token で防止し、クラッシュ後は旧プロセス停止確認のうえ手動復旧します。詳しくは [時間制バッチ v1.2](docs/timed-batch-v1.2.md) を参照。

## 重要：Sitesと学習ワーカーは別

ChatGPT Sitesには`@Sites`でサイトを作成できますが、PyTorch学習がSitesのランタイムで実行できるとは前提にしません。`live.html`と`live.js`をUI基盤とし、Sites内の認証・永続DBまたは認証済みの外部APIへ接続します。Python学習ワーカーは別ホストが必要です。具体的な引き継ぎは[SITES_PROMPT.md](SITES_PROMPT.md)と[docs/sites-handoff.md](docs/sites-handoff.md)を参照。

## v0.9: 投票締切・実験履歴の保全

- サーバー時刻基準のラウンド締切をSQLiteへ保存し、ワーカーが遅延しても締切後の推薦・取消・メモ変更を拒否します。
- 残り時間の表示・15秒ごとの状態自動更新を追加。サーバー時刻で時計ずれを補正します。
- ロールバック後も古いモデル評価を上書きせず、ラウンド固有の指標を保存します。
- CIFAR-10画像の公開にはmanifestの明示的な権利承認と設定の両方が必要です。
- 非公開ステージング用の[Compose実行手順](docs/sites-integration-v0.9.md)とGitHub Actions回帰テストを追加しました。

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

## デバッグ記録

- [2026-11-15 v1.0: 問題の再現、修正、回帰テスト](docs/debug-report-v1.0.md)

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

## One-command functional demo (v0.8, **real training on original synthetic pixel art**)

To test the whole game **without downloading CIFAR-10**, start the localhost-only
procedural training lab. The 1,600 generated 32×32 images are newly drawn by this
project; **these are NOT CIFAR-10 photos and their metrics say nothing about
CIFAR-10 accuracy**.

```bash
python -m pip install -r requirements-ml.txt
python -m backend.local_demo --port 8000 --round-seconds 90
```

Visit `http://127.0.0.1:8000/`. The browser can explore actual generated images,
search, vote on up to 10 samples per session, see other sessions' votes, and review
real PyTorch experiments when the round closes. The local worker runs both
Community and Random arms for 40 optimizer steps, evaluates them, applies the
safety gate and creates the next round. It is **not** a publicly authenticated
service. For another run use another `--state-root`; the default `demo-state/`
contains checkpoints and SQLite data and is gitignored. Stop using Ctrl+C.

**Sites:** Static-host build `dist/index.html` now serves the API-driven live page,
not the fabricated demonstration. Without a configured server the page will
show an explicit connection error and a link to `dist/demo.html` (local, simulated
UI-only). For a public Sites launch, connect genuine authentication, server-side
persistence and an external ML worker. This local command must not bind to
`0.0.0.0` or serve as the public production backend.

### Verification

```bash
npm run check && npm run build
python -m pytest tests_py -q
python tests_e2e/ux_flow.py                # Chromium UI + simulated API errors
PYTHONPATH=. python tests_e2e/ui_api_bridge.py  # Chromium UI ↔ real FastAPI, synthetic training
```

Local Chromium navigation to `127.0.0.1` may be blocked by the execution
platform. `ui_api_bridge.py` runs the *real* FastAPI app through separate
TestClient cookie jars bridged to Chromium UI requests. Image responses are
verified independently by `test_demo_mode.py`. This is a functional integration
check, **not** validation of browser networking in a deployed public site.
