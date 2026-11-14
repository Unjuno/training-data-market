# デバッグ報告 v1.0 — 2026-11-15

対象: v0.9 (7f15e8a) からの修正。

- BUG-01: 画像配信が毎リクエストCIFAR-10全体を再読み込み。5リクエストで5回、同時6リクエストで6回の構築を再現。アプリ内で遅延初期化しLockで排他。tests_py/test_image_cache.py で回帰防止。
- BUG-02: 43,000候補の検索が毎回全件読み込み。通常一覧・ラベル・画像ID検索をSQLiteのCOUNT/LIMIT/OFFSETに移動。誤分類フィルタは予測データに依存するため従来の絞り込みを残す。tests_py/test_sample_pagination.py で検証。
- BUG-03: HTML number入力で「1e2」が画像100への推薦になっていた。数字文字列のみ許容して異なるIDへの誤投票を防止。tests_e2e/ux_flow.py のChromium再現・修正。
- BUG-04: SQLのLIKE特殊文字による誤一致を防止するため、文字列の部分一致はinstrで実装。

## 検証コマンド

- npm run check
- npm run build
- python -m pytest -q tests_py
- python tests_e2e/ux_flow.py
- python -m tests_e2e.ui_api_bridge
- python -m compileall -q backend

## 未検証

- ChatGPT Sitesの本番公開と本人確認・多人数負荷試験
- 実CIFAR-10の学習性能、画像再配布権利
- Dockerビルドと永続ボリューム権限 (Docker未導入)
- 誤分類のみフィルタの大規模負荷 (通常一覧はSQL側に移行)

上記の未検証事項を本番対応済みと表現しない。
