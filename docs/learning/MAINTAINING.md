# 講義資料の更新・公開準備

講義本文は `01-lecture.md`、ブラウザ版は `01-lecture.html`。元の実習は `01-heated-cantilever.md`。本文・図の説明を変更した場合は両版の意味をそろえる。

M1の講義は `02-design-comparison.md`。GitHubで表示できるMarkdown表・Mermaid図と、既存の梁SVGを使用する。数値表を更新するときは同資料のPython例と比較CLIを再実行する。比較CLIは `run.cmd compare cases\heated_cantilever_comparison.toml`。M1の専用HTMLは未実装。

## ブラウザで読む

M2の導入資料は `03-fem.md` / `03-fem.html`。共通の `assets/lecture.css` と `assets/fem-mesh-and-order.svg` を使用する。M2aの梁FEMは実装済み、M2bは計画段階。ブラウザ版は要点、Markdown版は実行方法・検証基準・実際の計算結果を含む。テーマ以外の入力・個人の解答は保存しない。

M2aの数値図は独立した科学図としてMatplotlibで出力する。`run.cmd fem cases\cantilever_fem.toml --output outputs\new-fem.json` の後、描画用環境（任意依存 `.[figures]`）で `python scripts/plot_fem_results.py outputs/new-fem.json docs/learning/assets` を実行する。SVG/PNGと入力・結果JSONを一緒に更新し、図を目視確認する。CIは保存入力・コードと数値の再現を検査する。描画ライブラリはFEM実行の必須依存ではない。

M2ブラウザQAは `scripts/verify_fem_lecture.cjs`。後述のPlaywright環境で実行し、18表示条件、ローカルリンク、SVG文字範囲を確認する。結果はGit対象外の `outputs/fem-lecture-qa` に保存する。

GitHubのファイル画面ではHTMLはソース表示になる。clone／ダウンロード後、`docs/learning/01-lecture.html` をブラウザで開く。HTMLと `assets` フォルダを一緒に置く。外部フォント・CDN・API・Webサーバーは不要。将来GitHub Pagesで配信する場合にも相対パスで動作するが、Pagesの設定と一般公開は未実施。

表示テーマだけをlocalStorageに保存する。回答・個人の学習履歴は保存も送信もしない。

## 数値と比較表

Pythonのモデルを正として36ケースを生成する。ブラウザはその値を表示・単位換算する。別実装の物理ソルバーをJavaScriptに持たせない。

```powershell
.\.venv\Scripts\python.exe scripts\build_lecture_data.py
.\.venv\Scripts\python.exe scripts\build_lecture_data.py --check
.\.venv\Scripts\python.exe -m pytest -q
```

`assets/lecture-data.js` と本文の生成マーカー内は生成物。入力・モデルが変更されたら再生成してcommitする。CIで整合を検査する。

## 図と表示の確認

SVGは本プロジェクトで作成した概念図。寸法比を忠実に描く断面の比較図と、形状・変形を誇張した説明図を区別する。図に意味が変わる修正をしたら、力の向き・軸・境界・単位・代替テキストを確認する。

日本語は本文と見出しを同じ書体、字間ゼロで組む。固定した0〜8倍の軸を使い、温度倍率は温度差で計算する。グラフの色だけで合否を伝えない。印刷用の図は明るい背景に固定している。

任意のブラウザQAは `scripts/verify_lecture.cjs`。Playwrightが解決できるNode.js環境で実行する。`BROWSER_EXECUTABLE` でインストール済みChromium/Edgeを指定できる。`JAPANESE_PAGE_AUDIT` を指定するとローカルの日本語ページ監査も実行する。これらはQA時だけの環境変数で、講義の閲覧には不要。

QAは36ケースの数値表示と合否、幅320/768/1280、ライト・ダークのOS設定と3つのテーマ選択、SVG文字の範囲を検査する。スクリーンショットと監査結果は `outputs/lecture-qa` に出し、Gitには含めない。最後はスクリーンショットでも図の意味と表示を確認する。

## 公開時の確認

- 現在の公開範囲は非公開。一般公開とライセンス付与は、明示的な公開判断の後に行う。
- 個人の解答・会話・学習状況・ローカルの認証情報を教材へ含めない。
- 出典は元ページを示し、転載図・長文引用で教材を構成しない。
- 教材のAI支援、仮定、未評価項目、数値実装の検証と実機の妥当性を区別する。
- 数値再生成チェック、PythonのCI、ブラウザQAと目視を通す。

公開予定を理由に学習者の確認を省略しない。C1〜C4は教材では判定済みにせず、説明と本人の実行結果により別途確認する。
