# AstroText — 给 AI Agent 的纯文本占星排盘引擎 · 实施计划

## Context（背景与目标）

给定出生年月日时分 + 出生地 + 现居地，一条命令生成一个人的完整"占星档案"（纯文本目录）：本命、行运、次限、三限、太阳弧、日返、月返、法达、小限……供解读型 AI agent 直接阅读。核心难点不是天文学，而是**正确性可证明**：LLM 不会算数，所以引擎必须预先算出解读所需的全部数值与派生事实，并且每个数字都能对照权威源验证。

**已确认的三个决策**：① 档案用英文核心 + 中文术语对照表；② 西方（现代+古典）全套先行，印度占星为紧随其后的第二阶段；③ 交付到 GitHub 仓库（已验证：本会话的注入凭证能以 **KewenGu** 身份访问 GitHub API）。

## 第一性原理（设计公理）

1. **AI agent 不会算** → 文本中不留任何需要 agent 自行运算的空间：相位准确度、入相/出相、下次精确时刻、尊贵得分、互溶、盘主星链、日夜区分……全部预计算。
2. **一切技法都是三件地基事实的纯函数**：天体位置（星历）、时间换算（本地时→UT→TT/ΔT）、坐标与分宫。地基先被证明正确，九类盘只是组合。
3. **误差主要来自时区与地名，不是天文** → 历史时区库 + LMT 回退 + 解析结果回显在档案头供人工核对（已实测：系统 tzdb 正确处理 1986-91 中国夏令时）。
4. **正确性靠对照与不变量证明，不靠目测** → 同源逐位校验 + 异源交叉校验 + 数学性质测试，三层缺一不可。
5. **可复现** → 所有设置（黄道制/宫制/容许度/ΔT/引擎与星历版本）写入档案头；输出确定性排序、固定精度；同一输入永远逐字节相同。

## 环境实测结论（本次规划期间已验证）

- Python 3.11.15，numpy/pandas/pydantic 已装；gcc 13 + make 可用。
- **PyPI 和 npm 被网络策略屏蔽（403）**，但 **GitHub 完全可达**（git 协议已实测）。
- 因此依赖策略 = 全部从 GitHub 源码构建并 vendor：
  - `astrorigin/pyswisseph`（Swiss Ephemeris 官方 Python 绑定，与 astro.com 同内核）→ gcc 编译；
  - `aloistr/swisseph`（Astrodienst 官方仓库）→ 星历数据文件 sepl/semo/seas（1800–2399，可扩展）+ 恒星表 + **swetest 参考实现**（编译成 CLI 作对照标尺）;
  - `pytest-dev/pytest` 源码安装（纯 Python）；失败则回退 stdlib unittest。
- 运行时零外部依赖（stdlib + numpy + vendored pyswisseph）→ 完全离线、确定性。
- GitHub token 能认证为 KewenGu，但 scope 未知：M0 先尝试 API 建私有仓库；若无权限，请你在 github.com 手工建空仓库并授权，我推送。

## 架构（分层，Python）

```
L0 天文内核   pyswisseph 封装：黄经/黄纬/赤纬/速度/逆行/OOB，ΔT，岁差章动由 SE 处理
L0 时空解析   地名(含中文别名)→经纬度→IANA 时区→UT/儒略日；LMT 回退；歧义/不存在时刻检测
L1 盘核心     Chart(时刻, 地点, settings) → 行星 + 宫头(Placidus/WholeSign/Koch/Porphyry/
              Regiomontanus/Equal/Alcabitius/Campanus) + 四轴 + 相位引擎(容许度/入出相/精确时刻)
L2 技法层（全部是 L1 的纯函数）
   映射类：行运=当下时刻 | 次限(1日=1年) | 三限(1日=1月, Troinski 两种变体) | 太阳弧
   求根类：日返/月返/任意行星回归 —— 黄经环绕安全的区间求根，解到秒级
   时主类：法达(昼夜序+节点位置变体) | 小限(年/月, 含年主星) | [二期] Vimshottari 大运
   古典包：区分昼夜(sect/hayz)、五种必然尊贵(庙旺三分界面)+失势落陷、互溶接纳、
           希腊点(福点/精神点, 昼夜公式)、映点/反映点、月相与月空亡、行星时、恒星合轴
   [二期] 印度层：恒星黄道(Lahiri 等可选 ayanamsa)、27宿+pada、D1/D9/D10 等主要分盘、大运
L3 传统配置   modern / hellenistic / vedic 三个 profile：决定用点、宫制、尊贵、容许度、输出模块
L4 渲染      紧凑文本(主) + JSON(机读/测试用) + round-trip 解析器 + 中文术语对照表生成
L5 接口      Python 库 + CLI：一条命令 → 完整档案目录；[后续] MCP server
```

**现居地的用法**：本命恒用出生地；行运宫位与日返/月返默认以现居地起盘（占星通行做法），可切回出生地，档案头注明。

**仓库结构**：`src/astrotext/{ephem,timespace,core,techniques,profiles,render}` + `vendor/`（构建脚本+固定 commit）+ `data/`（地名库，注明出处）+ `tests/{golden,properties,cross,edge}` + `tools/`（fetch/build/verify 脚本）+ `docs/`（FORMAT.md、TECHNIQUES.md 逐技法引用出处、PLAN.md）。

## 档案 = 纯文本数据库（交付形态）

```
dossier/<person>/
  00_meta.txt        输入回显+解析后的经纬度时区(供核对)+全部设置+引擎版本+中英术语表
  index.txt          目录+每个文件怎么读(教 agent 的说明)
  10_natal.txt       行星表/宫头/四轴/相位(含精确度与入出相)/月相/昼夜盘/尊贵/接纳/希腊点/恒星合轴
  20_transits.txt    行运对本命：位置+相位+每个相位下次精确时刻
  21_secondary.txt   次限   22_tertiary.txt 三限   23_solar_arc.txt 太阳弧
  30_solar_return_2026.txt   31_lunar_return_2026-07.txt
  40_firdaria.txt    完整 75 年主/副周期表   41_profections.txt 年限/月限+年主星
  [二期] 50_vedic_*.txt
```

行星行示例（风格示意，M1 定稿）：`SUN 24°06'32" Gem | H10 | +0°57'14"/d | decl +23°17' | dig: peregrine`。批量模式：CSV 进 → N 个档案出。

## 里程碑（垂直切片，每片自带验证，每片一次 push + 交付物）

- **M0 奠基与最大风险拆除**：建 GitHub 仓库；编译 pyswisseph + swetest + 星历文件；时空解析管线（含中国历史时制案例）；测试骨架 + `make verify`；用 3 个已知案例证明行星位置与 swetest 逐位一致。→ 交付：可运行的最小内核 + 第一份验证报告。
- **M1 本命盘完整 + 文本格式 v0**：L1 全部 + 古典包 + 渲染器 + round-trip 解析器 + 黄金案例集（≥20 个，覆盖南北半球/高纬/1900 前/DST 切换瞬间/子夜/闰日/未知出生时间模式）。→ 你开始试读并反馈格式。
- **M2 推运族**：行运（含下次精确时刻计算）、次限、三限、太阳弧；四轴推进法可配置（默认对齐 astro.com 惯例）。
- **M3 回归与时主**：通用回归求根器（日返/月返/行星返照，含岁差修正变体开关）、法达、小限。
- **M4 西方验收冻结**：格式 v1 定稿、档案生成器整合、文档齐全、完整验证报告、性能与确定性断言。→ **西方全套验收点**。
- **M5（二期）印度层**：恒星制/ayanamsa、27 宿、主要分盘、Vimshottari；同等验证标准。
- Backlog：ZR、主限、中点、MCP server、更多小行星。

## 工程循环（loop engineering）

**模块级循环**（每个技法同一节奏）：写规格（含流派变体与文献出处，落入 TECHNIQUES.md）→ 实现 → 与 swetest 同源逐位校验 → 高风险公式由独立子代理"只看规格重推一遍"做对抗性复核 → 黄金案例 + 性质测试 + 边界测试 → 快照冻结进回归集 → push。

**里程碑级循环**：交付样例档案 + 验证报告 → 你（或你的解读 agent）用真实案例试读 → 反馈字段增删/格式问题 → v1 冻结前快速演进。格式带版本号，引擎 semver，CHANGELOG 记录一切行为变化。

**跨会话**：一切以 GitHub 仓库为准；每次会话开始 `git pull` 即恢复全部上下文（PLAN.md 里维护"当前进度+下一步"）。

## 测试与验收

**四层测试**：
1. **同源逐位**：行星黄经/宫头/四轴 vs swetest（同引擎同设置，应在 0.01″ 内逐位一致）——验证的是我们的封装、时间换算与设置无误。
2. **异源交叉**：JPL Horizons / astro.com 页面（M0 实测网络可达性，若被屏蔽则由你在 astro.com 抽查作 UAT）+ 权威出版物数值（法达/小限对照 Dykes、Brennan 等书中实例表）。所有差异必须给出解释。
3. **性质不变量**（种子随机大批量）：次限盘在 0 岁 == 本命盘；日返时刻太阳黄经与本命差 <0.1″ 且在正确年份窗口；太阳弧所有点位移严格等于次限太阳位移；宫头单调环绕、象限制 ASC==1 宫头；相位矩阵对称且 orb ≤ 上限；法达周期总和 =75 年且昼夜序正确；小限 n 岁与 n+12 岁同星座；渲染→解析 round-trip 数值全等；同输入输出逐字节相同。
4. **边界**：极圈 Placidus 失败→自动回退+警告；DST 造成的不存在/歧义本地时刻；1582 历法改革前（儒略历输入选项）；未知出生时间（正午盘/日出盘模式，禁用宫位输出并警告）。

**验收标准（M4，西方全套）**：上述四层全绿；`make verify` 自动生成 verification_report.md（每类盘 × 每个参照源 × 最大误差）；20+ 黄金案例快照回归零漂移；你在 astro.com 上抽查 ≥3 个真实案例（行星到分、宫头到分、返照时刻到分钟）逐项一致；完整档案生成 <5 秒。

## 主要风险与对策

- **GitHub 建仓权限未知** → M0 先试 API；不行则你手工建空仓，我推送（5 分钟内解决）。
- **JPL/astro.com 可能不可达** → 参照源阶梯：swetest（必可用）→ 出版物数值 → 你的 UAT 抽查。
- **地名库获取**（download.geonames.org 可能被屏蔽）→ GitHub 镜像 → 你下载后拖进对话 → 兜底：始终支持直接输入经纬度+时区。
- **1949 前中国多时区/民国夏令时** → LMT 模式 + 显式时区覆盖 + 档案头警告。
- **三限/法达等存在流派变体** → 绝不隐藏默认：全部做成显式开关，文档注明出处，默认值对齐主流软件。
- **Swiss Ephemeris 是 AGPL** → 私用无碍；将来若商业分发需购买 Astrodienst 许可或换内核（架构上 L0 已隔离，可换）。

## 验证方式（怎么确认这个计划做完了）

每个里程碑：跑 `make verify` 看全绿 + 读 verification_report.md + 我把样例档案（可用你提供的真实出生数据）发给你试读；M4 你在 astro.com 做最终抽查签收；M5 印度层用同一套流程（参照源换 Jyotish 权威软件/表）。



## V2 计划 — 换核:Swiss Ephemeris → DE440 + ERFA(详见 docs/KERNEL.md)

**动机**:做 AI agent 的 provider,内核必须宽松许可。市面上不存在高精度 MIT/Apache 占星引擎(flatlib/kerykeion/immanuel 全是 SE 包装)——自有内核即护城河。SE 行星本质是 JPL DE 的 ~0.001″ 压缩,直读 DE440 + ERFA 归算,物理相同、精度不降。

**决策**:生产内核 = jplephem(MIT) + pyerfa(BSD) + de440.bsp 节选(public domain, 1799–2400, ~40MB, 脚本拉取不入仓);Chiron 用 Horizons SPK;恒星用 Hipparcos。swetest 降级为 dev-only 参照并新增 Skyfield 第三方 → 验证升级为三方异源互证。SE 保留为可选 `backend="swiss"`(dev profile,AGPL 标注,不进发行物)。K8 整仓 AGPL→Apache-2.0。

**红线**:格式 v1 契约、技法语义、公共 API/CLI/MCP/HTTP 全部不动;engine → 2.0.0。手写部分(分宫全套、ΔT、平均交点/Lilith、ayanamsa 常数)一律 clean-room:只用公开文献 + SE 手册(描述文档)+ 黑盒输出,不开 SE 源码。

**里程碑**(每片自带验证 + push;验收细则、公差预算、风险表见 KERNEL.md):
- K0 探针:de440+pyerfa 跑通 太阳/月亮/火星 视黄经 vs swetest(≤0.01″)+ 性能实测 → 定生死
- K1 时间与坐标基建(ΔT 对齐 SE ≤0.01s@fixtures——ARMC 15″/s 是硬约束)
- K2 行星管线(lon/lat/dist/speed/RA/dec 全网格 ≤0.01″)
- K3 派生点(真/平交点、Lilith、Chiron)
- K4 分宫(8 制式 + 四轴 + 极地语义,vs swetest ≤0.001″)
- K5 恒星制(4 ayanamsa,vs swetest -sid ≤0.01″)
- K6 恒星 + 行星时(日出日落 ±1s)
- K7 切换验收:backend 开关、三方 verify、快照 diff 报告(预期 ≥95% 逐字节不变,余者末位 ±1″ 且逐条解释)、档案 ≤5s、2.0.0-rc
- K8 许可切换:vendor 拆分、Apache-2.0、NOTICE/README、发布 2.0.0

---

## 进度记录（跨会话交接）

### Session 1 — 2026-07-08
- **M0 完成**：源码构建体系（PyPI 被屏蔽 → 全部 GitHub vendored）、时空管线（中国历史时制全过）、L0 与 swetest 逐位一致（≤5e-8°）。
- **M1 完成**：本命层全套 + 文本格式 v0 + round-trip 解析 + 20 黄金案例快照；古典表格经独立子代理对抗性复核，零错误。
- **M2 完成**：行运（全部精确时刻，逆行 1-3 根全列）、次限/三限/小限推运、太阳弧、推进四轴两法；修正 progressed_moment 的 UT1/UTC 往返漂移（~0.2s）。
- **M3 完成**：通用回归（日返/月返/行星返照、岁差修正变体）、法达（昼夜序+节点两变体）、小限（以真实日返为年界）、行运月亮空亡。
- **M4 完成**：档案生成器 + CLI（`python -m astrotext dossier ...`）→ 12 文件个人文本数据库；270 测试全绿；`make verify` PASS。
- **未完成/下一步**：
  1. **推送 GitHub**：等用户建仓 `KewenGu/astrotext` 并把仓库加进会话 sources；本地 4 个 commit 待推。
  2. **M5 印度层**：sidereal/ayanamsa（SE 原生支持，engine.state 已有 extra_flags 通道）、27宿+pada、D1/D9/D10、Vimshottari（从月亮宿主起 120 年）。
  3. **UAT**：用户在 astro.com 抽查 2-3 个真实案例（行星到分、宫头到分、返照时刻到分钟）；名人 fixtures 的出生数据凭记忆，需对 Astro-Databank 复核。
  4. **待办小项**：GeoNames 离线地名库（中文别名）；三限 Troinski II 变体考证；VOC 现代变体开关；次限四轴对 astro.com 缺省的最终对齐（UAT 时定）；1200-1799 星历文件（会话内 GitHub 被限流，vendor.sh 已有自愈逻辑）。
- **环境备忘**：PyPI/npm 403；GitHub git 协议会话中途也变 403（vendor 需重试或换会话）；`make vendor` 从锁定 commit 重建一切。

### Session 1（续）— 同日
- **格式决策**：实测 JSON=2.48× 文本 token；定分工=text 喂模型 / JSON 喂代码，双视图默认并出（`--format`）。
- **M5 完成（印度占星层）**：原生 FLG_SIDEREAL 恒星内核（手减 ayanamsa 有 ~14″ 章动坑，已规避并写入文档）、27宿+pada、panchanga、全 Shodashavarga 16 分盘、8-karaka、Parashari drishti、Vimshottari 三级 819 段；档案 15 组文件；288 测试全绿；swetest -sid1 逐位一致；对抗复核零错误。
- **推送**：会话代理始终 403（仓库未绑入 session sources）；用户已建 public 仓库 KewenGu/astrotext 并用 bundle 推齐前 7 个 commit；M5 的新 commit 待用户从最新 bundle 推送。
- **下一步候选**：西方 UAT（astro.com 抽查）+ Vedic UAT（drik-panchang 抽查）→ v1 格式冻结；GeoNames 中文地名库；VOC 现代变体；MCP server 化。

### Session 2 — 2026-07-08 · UAT 交叉验证(sample: 1994-07-29 10:30 江阴,现居纽约)
- **起因**:用户在某 app 看到"太阳处女"与我方恒星巨蟹不符 → 确认为把 Lagna(本盘 18°28′ 处女)误读作太阳;真实生日 07-29(某网站输入 07-30 亦被识别出,全部数值与我方 +1 天外推一致)。
- **Vedic UAT 通过**:
  - drikpanchang.com(day-panchang, UTC+8):Tithi Krishna Saptami 05:09 起(我方 20.5% elapsed 折算 10:31 吻合)、Nakshatra Revati 至 17:40 / pada-3 至 10:58(出生 10:30 ✓)、Yoga Dhriti、Karana Vishti 至 18:14、月亮 Meena、**太阳 Karka(巨蟹)**、Surya nakshatra Pushya——逐项一致。
  - vedicastrochart.com(Lahiri/mean node, 用户手动复核过出生数据):九曜经度全部 ≤0.4″(多数 ≤0.05″),nakshatra-pada 9/9,whole-sign bhava 9/9,D9 varga 10/10;Lagna 差 ~1′(其城市坐标 120.2843/31.9192 vs 我方 gazetteer 120.2630/31.9110)。**Vimshottari 九个 mahadasha 边界全部 ≤1 天**(其 dasha 年长 365.256d vs 我方缺省 365.25d 的定义差),序列 Mercury(余 4.54y)→Ketu→Venus→Sun(2026-02-12 起)一致。
  - drikpanchang kundali 组件:grahas 与我方一致差 ~10″(其 True-Chitrapaksha vs SE Lahiri 定义差)、Rahu ~25″(节点模型差);其 Lagna 偏 ~16′ 属其自家恒星时/ΔT 约定(行星一致故非输入问题),我方 ASC 已由 astro.com 证实;其 Vimshottari 标签需登录,未取数。
- **Western UAT 通过(astro.com 官方在线 swetest 2.10.03)**:喂精确 jd_ut=2449562.60417523 后,行星(含 Chiron/Lilith/真节点)、12 个 Placidus 宫头、ASC/MC/ARMC/Vertex **全部 ≤0.1″**;裸 "02:30:00 UT" 输入时四轴系统性偏 ~10-11″,即我方经 swe_utc_to_jd 的 UTC→UT1(此日 +0.74s)修正所致——约定正确性得到确认。astro.com atlas 坐标(120°15′46.8″E, 31°54′39.6″N)与我方 gazetteer 完全一致。
- **结论**:v1 冻结前的 UAT 抽查完成(西方 astro.com ✓ + Vedic drikpanchang/vedicastrochart ✓,另有 astro-seek 由用户先行核对 ✓)。
- **待办沉淀**:MCP/HTTP 文档可加一条"解读须知:Lagna≠太阳星座"的教学注记(index.txt 已有雏形);dasha 年长变体(365.256/360)已是显式 knob,无需改动。

### Session 2(续)— 同日 · v1 格式冻结
- **v1 冻结完成(engine 1.0.0)**:`FORMAT_VERSION v0→v1`(text.py 单点常量;dossier meta/index 改用该常量)、JSON envelope `format_version 0→1`、parser 接受任意 `v<N>`;HTTP 路由前缀 `/v0/` 保留(REST 契约版本与文本格式版本独立)。
- 20+timed+vedic 黄金快照重生成(diff 仅第一行)、sample 档案重出;**323 测试全绿(6.6s)**、`make verify` PASS(engine 1.0.0)。全部在用户 Mac 本地环境执行(云端 GitHub 403,无法 vendor)。
- 文档:FORMAT.md 定稿为 v1(normative; frozen)、API.md 稳定性契约更新、README Status 更新、新增 CHANGELOG.md(1.0.0)。
- 待用户:git commit + push(建议单 commit:"Freeze text format at v1; engine 1.0.0")。注:_to_delete/ 目录为本会话产生的垃圾箱(stale index.lock、跑批脚本与日志),可整体删除。

### Session 2(续)— 同日 · V2 换核计划定稿
- 换核动机与路线定稿:**DE440 + jplephem + pyerfa 自有归算管线**,swetest 降级 dev-only 参照 + 新增 Skyfield 三方互证;SE 变可选 backend;K8 后整仓 Apache-2.0。完整 normative spec 落在 **docs/KERNEL.md**(管线、时间尺度、分宫 clean-room、公差预算、K0–K8、风险表),PLAN.md 本文件加 V2 总览章节。
- **下一步:K0 探针**(用户 Mac 一次性 venv:jplephem+pyerfa+de440 节选,3 天体 × ~20 时刻 vs swetest,拿误差与 µs/call 实数)。

### Session 3 — 2026-07-08 · 换核 K0–K2 完成
- **环境**:云端沙盒 PyPI/GitHub/JPL 全 403,但 osascript 可在用户 Mac 执行(真网络)→ 双环境工作流:Mac 抓数据/装依赖/跑 SE 真值与 git 提交,沙盒(Linux)写码跑测试(自建 Linux swetest;pyerfa 用 abi3 wheel 解包)。de440 节选(65MB, 1799–2400, SHA-256 pinned)+ jplephem/pyerfa sdist 落库(vendor/sdists gitignored;vendor/PINS.txt 记 pin;tools/fetch_kernel_data.py 可复取)。
- **K0 GO**:太阳/火星 ≤0.002″/0.0014″(同一 TT 喂两边);月亮近 J2000 ≤0.0025″、跨度边缘 0.030″ = **DE431(SE 数据源)→DE440 长期月历差**(非管线误差,日期剖面已录);向量化 15.6 µs/body-instant(预算 50)。
- **K1 完成**(src/astrotext/kernel/{timescales,frames}.py):ΔT 采用 **SE 2.10.03 黑盒 parity 网格**(§11 允许;SMH2016 样条系数 UKHO/RSPA 均取不到),8423 节点,随机 2 万点校验 ≤0.25 ms(验收 50 ms);实测并复刻三个 SE 行为:1955 前逐年线性+每年 1/1 ~1 ms 锯齿、utc_to_jd 内部用 JPLEPH 潮汐口径(与 SWIEPH 1955 前差 ~0.2s@1820)、2033 年冻结闰秒表失效转 UT1 语义;闰秒表嵌 USNO tai-utc.dat;日历双制 Fliegel/Van Flandern。utc_to_jd 5 千随机点 ≤0.21 ms。
- **K2 完成**(src/astrotext/kernel/bodies.py):十天体全归算(光时×2→太阳偏折→周年光行差→pnm06a→黄道真分点),速度用全管线 5 点差分(h=0.01d)。65 时刻网格:行星 lon/lat/RA/dec ≤0.0074″;月亮 0.030″(核心窗 1850–2150 ≤0.01″);dist ≤5e-9 相对。**发现并量化:SE 报告的速度 ≠ 其自身位置曲线的导数**(月亮差至 ~0.18″/day,与其文档精度一致;lat 速度全天体一致差 ~2e-5°/day)→ 速度验收改为对"SE 位置数值导数"(行星 ≤3.2e-7°/day 地板,来自 SE 内部章动插值)。**三方互证落地**:同一 de440 下 ours vs Skyfield 1.54 ≤0.0002″(行星)/0.0013″(月亮=TDB−TT 项,已记为可忽略)——比两者对 SE 都紧 30 倍,管线正确性与 SE 模型差分离。性能 11 µs/body-instant(共享 Frames 网格)。
- **测试**:新增 tests/kernel(299 个,全部无 SE 依赖,fixtures 黑盒生成)+ 原 323 → **622 全绿(Mac 7.6s)**;verify_report.py PASS;tools/verify_kernel.py = K 系列验收报告(K1+K2 PASS,Skyfield 段可选)。
- **提交**:205f900(K0)、3b7074b(K1)、1e56d2a(K2)+ 本收尾提交;git 操作须在 Mac 侧执行(沙盒对 .git 无 unlink 权限,锁文件要 Mac 清)。
- **下一步 K3**:真/平交点、Lilith(Meeus/Chapront 多项式,0.5″ 容差)、Chiron SPK(Horizons 生成,Mac 网络可达已验证);然后 K4 分宫(swehouse 保持不读,Holden/Munkasey 公式)。

### Session 3(续)— 同日 · K3 完成(kernel/points.py + chiron)
- **TRUE_NODE**:DE440 状态向量密切轨道根数(真黄道系,几何态);≤0.058″/全跨度、0.020″/1850–2150——月历 DE 分歧被 1/sin i≈11 放大所致;交点距离(密切椭圆在交点处半径,μ 取 DE440 头文件 GM)对齐 SE 至 6e-10 au。
- **MEAN_NODE / MEAN_APOGEE**:Meeus ch.47(ELP-2000)多项式 + Δψ;**Lilith 用 SE 手册 §2.2.1 的倾斜平轨道投影**(±7′ 投影项 + β=asin(sin i sin u),i=5.145396°)——对 SE ≤0.64″/1.61″(SE 自评其平点精度 ~1″,展示精度 1″);SE 对平点返回常数距离(已 pin:0.0025695553/0.0027106251 au)。
- **CHIRON**:Horizons type-21 SPK jplephem 读不了 → tools/fetch_chiron.py 抓原始矢量(109,765 态,1798–2400,SSB/ICRF/TDB)自拟合 64 天 Chebyshev(残差 3.5e-9 au=Horizons 自身噪声);接入管线为第 11 天体。对 SE:1880–2160 内 ≤1.02″、跨度边缘 ~3.5″=**轨道解代差**(SE 用旧解,我方为现行解,反而更准);按窗口 gate 并记录。
- **发现**:SE 平交点 1955 前…(ΔT 同款)无;新发现=SE 手册明示 Lilith 需投影(de Gravelaine 星历即因未投影而差数角分)。
- 测试 385(kernel)全绿;verify_kernel K1+K2+K3 全 PASS(Skyfield 段已在 Mac .venv 补装);fixtures 三份(timescales/bodies/points)。
- **下一步 K4 分宫**:ARMC=gst06a+东经、8 制式 vs swetest ≤0.001″、极地语义 byte-for-byte;然后 K5 恒星制。

### Session 3(续)— 同日 · K4 完成(kernel/houses.py)
- **实现**:纯向量几何 clean-room(天顶/北点/东点向量 + 大圆相交,不解三角恒等式);8 制式全部落地:闭式 ASC/MC/Vertex/EqAsc/Equal/Whole/Porphyry/Regiomontanus/Campanus,Koch=MC 半日弧对称位移的上升点(黑盒解出 θ±k·SA_d/3,k=1,2),Alcabitius=ASC 半弧时圆投影,Placidus=定点迭代(收敛阈 1e-11°)。
- **验收**:40 配置 × 9 纬度(含 ±66.99):8 制式与 swe_houses_armc **逐位一致(0.000000″)**,Placidus 0.0003″(迭代尾);四轴同精度。
- **极地语义逐条测定并复刻**:P/K 在 |φ|≥90−ε 一律 raise(SE 即便 MC 的 AD 存在也拒绝);ASC=黄道-地平交点取**东半球**者(固定叉积方向在极圈内会翻 180°);**R/C 的第 10 宫取子午圈交点的地平线上方者,而 O/A/W/B 保留 RA=θ 点**(逐制式实测)。
- **ARMC 时间链**:1886–2050 内对 SE ≤0.0014″;跨度边缘 SE 长期恒星时拼接自身偏离(1800:−0.36″、2100:+1.79″、2399:−8.5″)——**我方与 Skyfield 独立实现全跨度一致 ≤0.0005″**,故差异归 SE 模型,按窗口 gate(10″)记录。
- 测试 735(kernel)全绿;fixtures 四份;verify_kernel K1–K4 全 PASS。
- **下一步 K5 恒星制**:4 ayanamsa(lahiri/krishnamurti/raman/fagan-bradley)定义常数(t0, ayan_t0)自 SE 手册,vs swetest -sid ≤0.01″;注意 TECHNIQUES.md 已记录的 ~14″ 章动坑。

### Session 3(续)— 同日 · K5 完成(kernel/sidereal.py)
- **算法定谳(黑盒淘汰赛)**:SE 缺省(传统)ayanamsa = a0 + p_A(t) − p_A(t0),p_A 用 IAU-2006 黄经总岁差多项式(Capitaine 2003,公开)→ 全跨度四模式 ≤0.0031″;对照组:刚性 3D 基准点变换 0.05″、IAE-1989 多项式 1.3″、Vondrák 帧 0.05″——全被淘汰。
- **恒等式实测**:ay_true = ay_mean + Δψ(逐位);native FLG_SIDEREAL = tropical(真分点) − ay_true。M5 的"~14″ 坑"即口径混用,内核按构造免疫。
- **端到端**:恒星黄经 vs swe_calc:日/土 ≤0.0032″,月 0.036″(K2 月历差原样传导)。a0 = t0 处黑盒采样(lahiri 与手册值差 0.14″,fagan 手册散文值本身粗略、差 3.7″,已记录)。
- 测试 880(kernel)全绿;verify_kernel K1–K5 全 PASS。
- **下一步 K6**:恒星(Hipparcos 22 颗 + pmsafe 自行)vs sefstars ≤0.5″;日出日落(−0.8333° 盘心)±1s → 行星时。
