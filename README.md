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

既存のConda環境には依存を追加せず、専用 `.venv` を使う。実行部は標準ライブラリのみ。開発ツールとその依存は `requirements-dev.txt` に固定する。Linux側は次の通り。

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
tests/                    数値と統合の検証
docs/                     学習課題、拡張計画、設計判断、出典
```

## 次に読む

- [12分野と統合技術の学習ロードマップ](docs/roadmap.md)
- [第一ケースの式・前提・課題](docs/learning/01-heated-cantilever.md)
- [統合アーキテクチャ](docs/architecture.md)
- [初期構成を選んだ理由](docs/decisions/0001-analytical-baseline.md)
- [一次情報・既存技術](docs/references.md)

研究・学習の初期段階として非公開で開始する。公開範囲やライセンスは、開発・学習の進み具合を見て別途決める。
