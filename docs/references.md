# 一次情報と調査の入口

確認日: 2026-09-07。公開資料による機能調査であり、全製品を実操作・連携検証したものではない。

## 第一ケース

- [MIT OCW Structural Mechanics](https://ocw.mit.edu/courses/16-20-structural-mechanics-fall-2002/): 梁・構造力学を学ぶ講義の入口。
- [FunctionBay: A cantilever beam・式(5.41)](https://help.functionbay.com/2026/RecurDynHelp/Analysis/Analysis_ch04_s05_03.html): 一様片持ち梁の固有角振動数の解析式。Hzへは2πで割る。
- [NASA: Verification](https://www.grc.nasa.gov/www/wind/valid/tutorial/verassess.html) / [Validation](https://www.grc.nasa.gov/www/wind/valid/tutorial/valassess.html): 数値モデルの実装検証と、目的・適用範囲に対する妥当性確認の区別。
- [MIT: Intermediate Heat and Mass Transfer](https://ocw.mit.edu/courses/2-51-intermediate-heat-and-mass-transfer-fall-2008/pages/readings/): Fourier則と熱抵抗の学習入口。
- 応力・たわみはEuler–Bernoulli梁理論、定常熱伝導はFourier則から導く。実装式・境界条件・適用制限は [第一ケース](learning/01-heated-cantilever.md) に明記。

## M2：有限要素とメッシュの検証

- [SciPy: eigh](https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.eigh.html): 対称一般化固有値問題。実装では対称性・正定値を別途検査し、質量行列の逆行列を明示的に作らず解く。実行版はSciPy 1.16.2、NumPy 2.3.3に固定。

- [TU Delft: Euler–Bernoulli beam elements](https://interactivetextbooks.citg.tudelft.nl/computational-modelling/structural_linear/euler_bernouilli.html): 適合Hermite梁の連続性、2節点4自由度、三次変位補間。
- [TU Delft: FEM for an Euler–Bernoulli beam](https://interactivetextbooks.citg.tudelft.nl/computational-modelling/dynamics/Exercises/str_elem_dyn_workshops/Workshop_FEM_dyn_beam.html): 離散化、形状関数、剛性・質量、動解析への組み立て。
- [Abaqus: Bending benchmark](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEBMKRefMap/simabmk-c-linbending.htm): 次数・積分法・要素形状・ゆがみを変えた曲げ問題。製品固有の要素比較を普遍的な優劣へ一般化しない。
- [COMSOL: Mesh refinement study](https://www.comsol.com/support/knowledgebase/1261): h/pの変更、評価量を決めた収束確認。
- [COMSOL: Singularities when meshing](https://www.comsol.com/blogs/how-identify-resolve-singularities-model-meshing/): 特異点と局所応力、収束する評価量の区別。比較点はメッシュ依存の距離ではなく物理座標で固定する。

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
