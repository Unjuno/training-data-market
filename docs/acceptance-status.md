# Training Data Market v0.5 — 実装・検証状態（2026-11-15）

| 仕様条件 | 現状 |
|---|---|
| AC-01 CIFAR層化分割 | **合成ラベルで60,000件の検証PASS**。実CIFARで未実行 |
| AC-02 RGBテンソルと10クラス推論 | **合成テンソルの検証PASS**。実CIFARで未実行 |
| AC-03～06 推薦・重複・10件上限・締切 | **SQLite/HTTPテストPASS**。認証はブラウザ署名cookieのみ |
| AC-07/08 128件・投票最大64件・0票補完 | **純粋関数テストPASS** |
| AC-09/10 SGD二分岐と40更新 | **合成データのワーカー実行PASS**。実データは未実行 |
| AC-11 安全ゲート/ロールバック | **分岐条件テストPASS**。実データでの統計的校正は未実行 |
| AC-12 冪等・Workerリカバリ | 途中でLOCKEDを維持して再実行可能。障害注入は未実施 |
| AC-13 結果画面 | API連携コードを実装。実ブラウザE2Eは追加検証が必要 |
| AC-14 検証/テストの画像非公開 | 候補集合だけDBに登録。APIの画像配信は権利フラグfalseなら403 |
| AC-15 48件ページング | APIテストPASS。実43,000件で負荷試験が必要 |
| AC-16 画像公開権利ゲート | APIフラグで明示的にブロック。権利判断そのものは未確認 |
| AC-17 公開後のラウンド履歴 | SQLite永続化と次Round生成のテストPASS。クラウドで未試験 |
| AC-18 モバイル/キーボード | HTML/CSSの実装のみ。端末・ブラウザE2E未確認 |

### 検証環境

- Python 3.13.5、PyTorch 2.10.0+cpu、torchvision 0.25.0+cpu、FastAPI 0.128.2、NumPy 2.3.5
- Node.js 22.16.0、CPUバックエンド、バッチ32、初期5 epoch／追加10 epoch・40 steps/arm
- PythonとJavaScriptの単体/結合テストを実行。**性能ベンチマークと学習時間中央値の測定は未実施**。
- 実験結果・Lossの改善を作り込んだ架空の本番値は一切作成していない。

### 残る公開ブロッカー

本人確認済みユーザー認証、画像公開権利の確認、Sitesのサイト作成と非公開プレビュー、外部学習ワーカーの継続実行環境、実CIFAR-10での受入テストが必要。


## v0.6 フロントエンドデザイン検証

- 既存の日本語ライブ画面を研究コックピット形式にリデザイン。入力・一覧・推薦・結果・説明を統一。
- ローカルChromiumへの静的HTML/CSS描画により1440/820/390pxで横はみ出し0、ページJSエラー0を確認。
- デモの選択・解除・猫クラス検索のUI挙動を確認。隔離ブラウザではstorageにアクセスできず、保存操作は明示的に失敗を表示。
- Python/Node単体およびAPIテストは現行のツール環境で実行（成果物公開前に再実行）。
- **未検証**：Sites上のブラウザE2E、実CIFAR-10学習と画像公開権利の承認。

## v0.8 tested fixes (2026-11-15)

- Added original synthetic 32×32 pixel-art dataset and an explicitly marked
  `SYNTHETIC_PIXEL_ART` **DEMO** result source. It can run without CIFAR download.
- Added localhost-only one-command `backend.local_demo`, with actual gradients,
  real shared SQLite picks, scheduled lock, two arms, safety gate, and next round.
- Corrected static build entry: `/index.html` = live API screen;
  `/demo.html` = simulated UI only. Connection errors show a visible fallback.
- The image API serves only internally generated demo artwork when explicitly in
  demo mode, or CIFAR images when publication is separately authorized.
- Full API integration test checks two session IDs, SQLite persistence, note,
  40 real gradient steps per arm, round lock, result and new round.
- Chromium + real FastAPI bridge test checks the UI against real API responses.
- **Not verified:** official CIFAR-10 accuracy (dataset unavailable in this
  environment), direct browser-to-localhost navigation (admin policy blocked),
  deployed ChatGPT Sites, external-worker hosting, public authentication,
  actual human usability tests, official-image publication rights.

## v0.9 updates (2026-11-15)

- [PASS locally] Persisted per-round deadline and backward-compatible SQLite migration. Voting and notes are rejected with HTTP 409 at and after deadline, even before the worker locks.
- [PASS locally] The scheduler uses the DB deadline, not a different CLI timeout; the next round inherits the duration. Browser renders a countdown corrected using `server_time` and checks current round every 15 seconds.
- [PASS locally] Rollback retains the original checkpoint's metric file. Each next round has its own `metrics/round-XXXX.json` and `predictions/round-XXXX.json`, with legacy fallback.
- [PASS locally] Natural-image publication requires `image_rights_status=APPROVED` in the private manifest plus `TDM_PUBLISH_IMAGES=true`. Procedural local demo remains separate.
- [PASS locally] `npm run check` (20 JS tests), `npm run build` (15 public files), `python -m pytest tests_py -q` (30 Python tests), `python -m tests_e2e.ux_flow`, `python -m tests_e2e.ui_api_bridge` (real FastAPI TestClient + Chromium).
- [PASS local HTTP] Uvicorn started with procedural data; two cookie-separated clients cast votes, the public count reached 2; deadline expiration returned HTTP 409, then the worker performed 40 updates per arm and created a new round (synthetic dataset only).
- [NOT TESTED] CI on GitHub runners, Docker image building (Docker unavailable in current container), public Sites preview, end-user identity verification, real CIFAR-10 performance and image-publication rights.
