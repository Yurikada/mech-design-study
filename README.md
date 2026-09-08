# mech-design-study

機械・電気・信頼性に関わる**個別の設計技術**と、評価結果をつないで判断する**統合の仕組み**を、実装と検証を通じて学ぶスタディケース。

初期版は「加熱される片持ち支持板」。共通の寸法・材料入力から、応力・たわみ・一次固有振動数・定常温度を計算し、制約の余裕を表示する。ケースの全12分野のうち評価済みは3分野。残りは `not_evaluated` で、総合結果は `incomplete` となる。

**学習用の解析解モデルであり、実機の安全性・寿命・EMC適合を検証した設計ツールではない。** 入力の物性と閾値は学習用の仮定で、認証済み材料データではない。初期コード・説明・テストはAI支援で作成した。動作確認と本人の技術理解は別の達成条件として管理する。

## 最初の15分

1. 下記手順でセットアップし、基準ケースを実行する。
2. `cases/heated_cantilever.toml` を `cases/my_first_case.toml` にコピーする。
3. 板厚を3 mmから2 mmへ変える前に、応力・たわみ・周波数・温度がどちらへ変わるか予想する。
4. 変更したケースを実行して、予想と制約違反を照合する。
5. [最初の学習課題](docs/learning/01-heated-cantilever.md)に沿って、式の意味とモデルの限界を自分の言葉で説明する。

## Windowsセットアップ

Python 3.12以上が必要（このPCの基準はPython 3.13）。リポジトリ直下のPowerShellで実行する。WindowsAppsのPythonエイリアスが不調な場合は実在するPythonを指定する。

```powershell
& .\scripts\setup.ps1 -PythonExe "$env:USERPROFILE\miniconda3\python.exe"
.\run.cmd
.\run.cmd cases\my_first_case.toml
.\run.cmd cases\heated_cantilever.toml --json
```

スクリプト実行が端末の設定で制限される場合は、ポリシーを変更せず以下を直接実行できる。

```powershell
& "$env:USERPROFILE\miniconda3\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-build-isolation -e .
.\.venv\Scripts\python.exe -m pytest -q
.\run.cmd
```

既存のConda環境には依存を追加せず、専用 `.venv` を使う。解析解と比較の計算部は標準ライブラリ、梁FEMはNumPy/SciPyを使う。開発ツールと実行依存は `requirements-dev.txt` に固定する。Linux側は次の通り。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install --no-build-isolation -e .
.venv/bin/python -m pytest -q
.venv/bin/python -m mech_design cases/heated_cantilever.toml --json
```

## 基準ケースの結果目安

| 指標 | 計算結果 | 学習用閾値 |
|---|---:|---:|
| 質量 | 24.3 g | 目的候補。合否判定なし |
| 根元の公称曲げ応力 | 約2.22 MPa | 30 MPa以下 |
| 先端たわみ | 約0.0705 mm | 0.1 mm以下 |
| 一次固有振動数 | 約246.8 Hz | 200 Hz以上 |
| 先端温度 | 約304.80 K（31.65 ℃） | 313.15 K以下 |

これは正しく設定された玩具モデルの参照値。実機ではない。静的先端力と動的先端質量は別で、現在の周波数式は付加質量を含まない。熱モデルは根元温度固定・側面断熱の一次元熱伝導。対流、熱応力、温度依存物性は未実装。

CLIの終了コード: `0` = 評価できた項目は合格（未評価を含み得る）、`1` = 入力／計算エラー、`2` = 制約違反。`--require-complete` を付けると未評価が残る場合は `3`。自動判定で完全評価を要求するときは必ずこのオプションを使う。

## M1：複数案を比較する

```powershell
.\run.cmd compare cases\heated_cantilever_comparison.toml
.\run.cmd compare cases\heated_cantilever_comparison.toml --output outputs\comparison.json
.\run.cmd compare --replay outputs\comparison.json --json
```

比較TOMLは共通の基準ケースと、各案のID・長さ・幅・厚みを指定する。材料・荷重・熱条件・性能閾値は共通。各案への荷重などの上書きは拒否し、変更された項目名を表示する。基準ケースへの相対パスは比較TOMLの場所を基準に解決する。

教材の4案ではA・Cが今回の制約を満たし、最軽量候補はA。Bはたわみと周波数、Dは長さの要求に違反する。`eligible` は今回の比較条件に限った候補で、9分野が未評価の `physical_overall=incomplete` と併記する。

`--output` は完全なJSONを新規ファイルへ保存する。既存ファイルを上書きしないため、再実行時は別の出力名を指定する。保存結果には全入力、要求版、モデル版、境界条件、指標・単位・閾値・margin・未評価、入力とコードのSHA-256を含む。`--replay` は元のTOMLなしで保存入力から再計算する。コードが変わった場合は再現計算を拒否するため、元のGitリビジョンを使用する。

比較コマンドの終了コードは `0` = 計算が正常終了して候補がある、`1` = 入力・計算・出力エラー、`2` = 候補なし。`--require-complete` では、候補があってもいずれかの案に未評価があれば `3`。除外案の存在だけでは `2` にしない。計算エラーが残る場合は他案の結果を保持するが、最軽量候補を確定しない。

Linuxや任意の作業ディレクトリからは、インストール済みPythonで `python -m mech_design compare <比較TOMLのパス>` を使える。[講義2](docs/learning/02-design-comparison.md)で入力・出力と判断を確認する。

## M2a：梁FEMを検証する

```powershell
.\run.cmd fem cases\cantilever_fem.toml
.\run.cmd fem cases\cantilever_fem.toml --output outputs\my-fem.json
.\run.cmd fem --replay outputs\my-fem.json
```

既存環境へ更新するときは `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` と `.\.venv\Scripts\python.exe -m pip install --no-build-isolation -e .` を実行する。M2aには固定版NumPy 2.3.3とSciPy 1.16.2を使う。

三次Hermite梁・整合質量・根元完全固定の静解析と第1〜3モードを、1/2/4/8/16要素で計算する。たわみ・反力・モード形状・解析解誤差・無次元残差・設定とメッシュをJSONに保存する。1要素の第3モードは自由度不足で未評価。保存ファイルは新規作成のみ、再計算には保存時と同じコード・NumPy/SciPy版が必要。

FEM検証の合格と設計全体の合格は別。梁の応力・たわみ・周波数は最細分割のFEM値、熱は従来の解析式で評価し、残る9分野は未評価のまま。終了コードは0 = 検証成功・評価済み制約合格、1 = 入力/計算/出力エラー、2 = 検証または設計制約違反、3 = 検証材料不足。`--require-complete` では未評価分野が残る場合も3となる。

[講義3の実測結果と図](docs/learning/03-fem.md)を参照。M2bの2次元要素比較は今後の課題。

## 開発と検証

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

GitHub ActionsでUbuntu/Python 3.12とWindows/Python 3.13を検証する。テストは手計算参照値、板厚による変化、熱収支、入力単位の誤り、未評価と合格の区別、CLI終了コードを対象とする。

## 構成

```text
cases/                    SI単位をフィールド名に含むTOML入力
src/mech_design/case.py    入力スキーマ・適用範囲チェック
src/mech_design/models.py  個別の物理モデル
src/mech_design/evaluation.py  共通の制約評価・未評価管理
src/mech_design/cli.py     ケース実行・JSON結果
src/mech_design/comparison_input.py  共通条件・要求・寸法案の入力
src/mech_design/comparison.py  比較・入力保存・再現計算
src/mech_design/comparison_cli.py  比較表・JSONの表示
tests/                    数値と統合の検証
docs/                     学習課題、拡張計画、設計判断、出典
```

## 次に読む

- [図付き講義：式から設計判断へ](docs/learning/01-lecture.md) / [ブラウザ版（clone後に開く）](docs/learning/01-lecture.html)
- [講義2：制約を満たす設計案を比較する](docs/learning/02-design-comparison.md)
- [講義3：メッシュ・要素形状・次数を選ぶ](docs/learning/03-fem.md) / [ブラウザ版](docs/learning/03-fem.html)
- [講義の閲覧・更新・公開準備](docs/learning/MAINTAINING.md)
- [12分野と統合技術の学習ロードマップ](docs/roadmap.md)
- [第一ケースの式・前提・課題](docs/learning/01-heated-cantilever.md)
- [統合アーキテクチャ](docs/architecture.md)
- [初期構成を選んだ理由](docs/decisions/0001-analytical-baseline.md)
- [一次情報・既存技術](docs/references.md)

2026-09-08にGitHubリポジトリを公開した。配布ライセンスは未設定で、別途決定する。
