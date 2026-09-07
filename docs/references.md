# 一次情報と調査の入口

確認日: 2026-09-07。公開資料による機能調査であり、全製品を実操作・連携検証したものではない。

## 第一ケース

- [MIT OCW Structural Mechanics](https://ocw.mit.edu/courses/16-20-structural-mechanics-fall-2002/): 梁・構造力学を学ぶ講義の入口。
- [Oxford: Structural vibration資料](https://eng.ox.ac.uk/media/9248/sim.pdf): 一様片持ち梁の固有振動数とモードを確認する資料。
- 応力・たわみはEuler–Bernoulli梁理論、定常熱伝導はFourier則から導く。実装式・境界条件・適用制限は [第一ケース](learning/01-heated-cantilever.md) に明記。

## 統合と形状探索

- [Ansys optiSLang](https://ansys.synopsys.com/en-gb/products/connect/ansys-optislang): 解析のプロセス統合・設計最適化。
- [COMSOL Optimization](https://www.comsol.com/optimization-module): パラメータ・形状・トポロジー最適化と物理モデルの接続。
- [SIMULIA Isight](https://www.3ds.com/products/simulia/isight): 商用CAE、自作コード等の統合。
- [HEEDS Systems MDO](https://blogs.sw.siemens.com/simcenter/introducing-heeds-connect-systems-mdo/): 分野別スタディの依存・連携。
- [nTop](https://www.ntop.com/software/capabilities/topology-optimization/): 形状最適化と製造制約。
- [DTU TopOpt](https://www.topopt.mek.dtu.dk/apps-and-software/efficient-topology-optimization-in-matlab): 標準問題と教育用コード。再利用時はライセンスを確認する。
- [OpenMDAO](https://openmdao.org/): 多分野解析・最適化を構成するオープンソース基盤。

## 専門モデルと作業性

- [CalculiX](https://www.calculix.de/): 構造・動解析・熱の外部ソルバー候補。
- [COMSOL Fatigue](https://www.comsol.com/fatigue-module): 疲労モデル。
- [COMSOL Corrosion](https://www.comsol.com/corrosion-module): 腐食と他物理の接続。
- [COMSOL Nonlinear Structural Materials](https://www.comsol.com/nonlinear-structural-materials-module): クリープ・粘弾性等。
- [Ansys EMI/EMC](https://www.ansys.com/content/ansysincprogram/en-us/home/applications/emi-emc.html): 電磁場解析と設計チェック。
- [Process Simulate Human](https://www.siemens.com/en-us/products/tecnomatix/human-centered-design-simulation/): 組立・保守の到達性や人間工学。
- [DFMA](https://www.dfma.com/software/): 製造・組立効率の評価。
- [KiCad/ngspice](https://www.kicad.org/discover/spice/): 既定回路のシミュレーション。
- [openEMS](https://www.openems.de/): FDTD電磁場ソルバー。

## 開発ツールの基準版

- [pytest 8.4.2](https://docs.pytest.org/en/stable/announce/index.html)
- [Ruff 0.12.12](https://pypi.org/project/ruff/0.12.12/)

基準版を固定して再現する。最新版の採用を目的とはしない。
