# 文案审核记录（2026-09-08）

审核基线：`main` / `a66ecf639a48208120eff5fc4c0f30c902173af5`。
按讨论逐项记录，区分明确冲突、歧义和需要确认的政策选择；实现用于核对现状，不自动视为规则权威。
本文是历史问题与决定记录，包含已废弃的原文引用；现行规则以 `rules/` 为准，当前验收待办以 `docs/pre-launch-checklist.md` 为准。
前期文案修订后，2026-09-09 用户要求开 PR。本次同时完成六题排名配置同步；未修改内存执行逻辑或 sair-server。
以下原文行号以审核基线为准，修改后的行号会变化。
本文末尾追加了 2026-09-09 的第二轮审核（W14–W31），基线为 W01–W13 修订后的 `491cb77`，只记录本轮未覆盖的问题。

## 2026-09-09 主办方讨论后的决定

### 后续 PR 的落地状态

本次修复位于 `codex/apply-organizer-decisions`，基于原 W01–W13 PR 的分支。
下面的会议记录保留决定刚收到时的状态；截至本次修复，实施状态如下：

| 范围 | 本仓库已完成 | 仍待完成 |
|---|---|---|
| W14，关联 W01/W06 | 九题独立 Python 标准答案、批次预计算命令、官方 wrapper 私密 stdin 传输、规格与完整计划校验、cohort 答案摘要；kernel 仍直接检查选手实现 | sair-server 接入新参数，官方容器与正式数据验收 |
| W03/W16/W17 | 九题 `full-plan-v1` 配置、100/0 分和无限成本排序、保留分题 T/T+C、旧契约兼容、规则与表格同步 | 平台排名字段同步，生产批次验证 |
| W20/W22 | Standard 2 / Light 5 的次数已写入规则，未确定的计数口径显式待公布 | 明确额度范围、正式提交关系及扣退规则后配置平台 |
| W05/W12 | UTC 日末分界、日榜生成时间和覆盖日期要求已写入规则；本仓库报告显示 UTC 生成时间 | 平台日榜调度与页面同步，确定发布时间与最终评测日程 |
| W24 | 比赛期间代码保密、赛后公开已写入规则 | 确定公开版本、许可和条款 |
| W23 | 已核对参考仓库并明确组织范围待澄清 | 主办方定义组织单位；未擅自删除组织限制或宣布大学例外 |
| W11 | overview/prelaunch 同步暂定 9 月 15 日 22:00 PT / 9 月 16 日 05:00 UTC | 平台开场配置；后续调整时统一更新 |

本 PR 未替主办方确定各题内存数值，也未修改固定 4 GiB 的运行约束；W08/W15 继续待办。
第二轮原始审核的其他建议不因本次 PR 自动视为已认可或已修复。

验证记录：

- 全部 Python 测试 205 项：204 项通过，1 项因未安装可选 SymPy 跳过。新增测试覆盖九题全部/部分/零通过排序、标准答案与 Lean 规格对照（含 polydisc 最大宽度）、错误答案被 kernel 拒绝、W14 的 well-founded 实现、答案封存与完整性检查、UTC 报告时间。
- 快速 Lean harness：16/16 个 manifest 示例通过。使用每组 1 个输入、1 次 wall-time replay 和开发限时，不代表全部正式用例或 PMU 验收。permanent 基线本次 2/3 个输入通过，按新规则显示 0 分、无限排名成本。
- 单独预计算并通过 stdin 传入答案文件，运行 fib/doubling 完整 6 输入开发计划：6/6 通过，核对 verdict 中答案摘要与输入文件一致。
- Bash 语法、Python 编译和 `git diff --check` 通过；未在本机执行正式 Docker/PMU 验收。

### 会议记录

来源：用户本日转述的主办方结论。以下为后续修改依据，优先于本文较早的建议；
“决定已确认”不表示 `rules/`、judge、scorer 或平台已经完成同步。本次先记录决定和实施范围，
不把旧 PR 的验证结果当作这些新政策的验收结果。输入更新的运营周期继续不在仓库记录。

| 议题 | 当前决定 | 关联问题与落实位置 |
|---|---|---|
| 标准答案 | 官方用独立参考程序、预计算表或其他方式提前准备隐藏输入的标准输出；不再执行选手的 `impl` 来获取该输出 | W14，连同 W01/W06 的失败归因；LKC judge、答案准备与封存流程、评测说明 |
| 分数与排名 | 每题全部输入通过才得 100 分并比较有限指令成本；任一输入失败，该题为 0 分、排名成本视为无穷大 | W03/W16/W17；九题配置、LKC scorer、规则及平台榜单 |
| 每日限额 | Standard 2 次，Light 5 次 | W20/W22；计数范围和正式提交是否共用额度仍待明确，再同步规则与 sair-server |
| 日榜分界 | 每日以 UTC 23:59:59 为日末分界；榜单必须显示生成时间 | W05/W12/W22；LKC 日榜说明、sair-server 调度与 sair-webs 展示 |
| 代码公开 | 比赛期间不公开选手代码，赛后公开 | W24；公开哪些版本、许可与平台条款仍须补齐 |
| 组织与队伍 | 参考 Equational Theories Stage 2 的规定 | W23；参考原文与 LKC 相同，尚不能解决大学是否算一个组织的问题，见下文 |
| 上线时刻 | 暂定 2026-09-15 22:00 PT（America/Los_Angeles），即 2026-09-16 05:00 UTC；后续可能调整 | W11；overview、prelaunch、平台开场配置；不改变最终提交截止时间 |

### 标准答案与 kernel 检查（W14）

确认的流程是：官方为隐藏输入准备标准输出 `v`；每份提交先通过
`impl_correct : ∀ n, impl n = spec n` 的证明检查；随后 kernel 检查并计量每个输入上的
直接等式 `impl n = v`。答案准备可在接收提交前完成，同一评测批次使用相同的输入与答案。

这项决定替代 W14 原先“提高 Meta 透明度，或收紧 R2”的二选一建议。
选手无需为官方取值器额外解封定义；R2 的 kernel 可归约要求仍然适用。
预计算只省掉用选手实现准备候选答案的步骤，不省掉目标定理检查和计时 replay 中对
`impl n` 的实际归约，也不能用已有的通用正确性证明代替被计量的直接归约。

实施时应将标准答案绑定到对应的题目规格版本、完整输入计划和评测批次，校验输出类型与完整性。
参考答案缺失、格式错误或与规格不符属于官方评测问题，不能因此给选手记失败或 0 分。
Python 或查表无需成为 Lean 的受信任证明步骤；最终直接等式仍由 kernel 检查。
这不构成“预计算绝不会出错”的保证，必须验证独立参考程序与规格的一致性。

当前 `judge/judge.py` 仍通过 `_eval_impl_value` / `_VALUE_META` 执行选手实现取值；
尚未接入独立标准答案。本项属于 LKC 评测实现改造，平台负责任务与数据衔接。

### 全部通过才比较成本（W03/W16/W17）

在正确性和评测记录有效的前提下，每题改为：

- 完整隐藏计划全部通过：100 分，按该题的指令成本从小到大排名。
- 任一输入因选手实现超时、超内存或其他有效失败而未通过：0 分，排名成本视为无穷大。
- 不再给部分通过的组别计分，也不再以较难组分数、通过数量或通过顺序区分这些 0 分提交。
- 完全相同的竞争指标保持并列。基础设施错误、遗漏用例和被中断的评测仍须处理或重评，
  不能伪造为完整的 0 分结果。未通过正确性门禁的提交仍是 rejected。

这明确选择了“全部通过是门槛，指令数区分名次”的赛制。基线能拿满分本身不再视为缺陷，
也不再以“必须让基线拿不到满分”为由上调难度。是否在正式主机与各题内存限额下全部通过，
仍须实测，不能从本地开发成绩推断。

本次没有提出取消 W03 已确认的分题成本政策：六题比较目标 replay 中位数之和 `T`；
`saw`、`ca-rule110`、`sha256` 比较 `T + C`，其中 `C` 是正确性闭包 replay 中位数。
不恢复独立的第五步 correctness 比较；正式排名仍使用指令数，不将本地 wall-time 与其混排。
正确性 replay 自身失败的既有判定未被“某个 input 失败”的决定自动改写。

需要整体替换现行的组别里程碑排名契约，而非只在文字中追加一个“无穷大”：
更新九题配置、`scripts/score.py`、契约校验与测试，以及 overview/evaluation/problem-scoring/README。
输入组仍可用于定义规模、用例数和资源限制，但旧的 20/30/50 分、组别前置条件和部分通过排序
不再决定名次。新旧评分契约不得混排；平台结果字段和展示也须同步。

W17 的分组定价争议随部分分取消而失去适用性；Spec 支持的范围与比赛采样范围仍可解释清楚。
W18 的样本代表性与成本波动问题仍可实测，但不再采用“按通过数给部分分”这一旧建议。

### 配额、日榜与公开范围（W20/W22/W24/W12）

Standard 2 次、Light 5 次这两个数已确认。尚不能据此判断是每队所有题合计还是每队每题，
也不能确定正式提交另有额度还是共用 Standard 额度。拒绝、取消、平台重试的扣额与退额规则
亦未在本次决定中给出；不得从测试环境临时调高的配置推导正式政策。

日榜的日期按 UTC 划分。实现应使用当天 `00:00:00 UTC`（含）到次日 `00:00:00 UTC`（不含）
的区间，以完整纳入 `23:59:59` 这一秒内的提交，避免有小数秒精度时漏单。
按平台记录的提交时间选择每队每题的 latest，不能改用评测完成时间，也不回退旧的成功提交。
日界线确定的是提交归属，不保证在同一瞬间完成计算或发布新榜。
用户要求显示榜单生成时间；建议同时显示所覆盖的提交日期或截止时间及 UTC 时区，
避免把“今天生成的榜单”误解为“包含今天所有提交”。此前讨论的延迟一天展示方案与
具体发布时间需在最终调度说明中明确；本次没有确定一个新的发布时间。

代码公开的时间原则已确认，W24 不能整体标为完成：仍需指定是最终选定版本、上榜版本还是
所有历史提交，以及对应许可和授权条款。不能因为仓库采用 Apache-2.0，就推定平台收到的
所有选手提交已按该许可授权。具体公开时间随最终公布日程确定，W12 仍有待办。

### 组织的定义（W23）

已读取参考仓库的
[`rules/overview.md` — Team Participation and Anti-Cheating Policy](https://github.com/SAIRfoundation/equational-theories-lean-stage2/blob/main/rules/overview.md#team-participation-and-anti-cheating-policy)。
原文是：

> Each individual or organization can participate in only one team.

相邻条款要求预先登记队员与赞助方，并对协同作弊（含马甲队伍）取消相关队伍资格。
这与 LKC 当前三条规定相同；参考文本没有定义 organization，也没有大学或实验室的例外。
因此，参照该仓库保留原文并不等于已经确认“同一大学可以有多个独立队伍”。

供后续确认的建议：限制同一人重复参赛和同一实际参赛实体通过多个队伍重复参赛；
仅有共同大学或上级机构隶属关系，不自动视作同一队伍。此建议尚不是已确认规则，
不擅自把 organization 删除，也不新增按大学整体限制参赛的解释。

## 本次 PR 的处理状态

| 事项 | 已处理 | 剩余工作 |
|---|---|---|
| W01/W02/W06 | 区分单用例值生成失败、整次评测错误、重评动作与 R2 违规 | 无新增实现承诺 |
| W03 | 六题配置改为 target work + correctness gate，三题保留 combined work；补充实际配置的排名回归测试 | 官方主机 cohort 演练 |
| W04 | 统一预上线时态与验收要求 | 真实生产验收及完成记录 |
| W05 | 临时榜与最终选稿统一 latest，不回退旧稿 | sair-server 按发布后的规则对齐 |
| W07 | 构建说明按 manifest 实际检查范围改写 | 无额外的“所有性能用例通过”保证 |
| W08 | 明确各题独立、可调整且按 cohort 固定的内存政策 | 确定数值并同步配置、wrapper、judge、scorer 和资源归因 |
| W09 | 限定最终正式数据公开承诺，临时参考输入政策保持隐藏 | 不在仓库记录运营轮换周期 |
| W10 | 删除现行评测规则中的原始 n 拟合介绍 | 不更改历史报告诊断代码 |
| W11/W12 | 统一标记开场时刻/时区、评测窗口、结果公布安排待公布 | 组织者确定并公布实际日程 |
| W13 | 旧组别与测量说明归档，当前清单引用现行政策 | 按现行政策完成生产验证 |

## W01 — 候选值不受支持与候选值错误的处理被混为一谈

- 状态：文案已修正；明确分开单用例值生成失败和整次评测错误。
- 位置：`rules/evaluation.md:25-29`、`rules/evaluation.md:78-81`。
- 原文：第一处说值为 wrong 或 unsupported 时整次运行不计分；第二处说不能生成整数常量仅使该用例失败，后续继续，零个通过也可以得到有效的 0 分。
- 实现核对：`judge/judge.py:2667-2669` 将值生成失败记为单用例 `value-eval-error`；`:2694-2695` 将生成定理的非资源性构建失败作为整次评测错误。
- 建议方向：明确分开“无法生成支持的常量”与“生成的定理不能通过 kernel 检查”。前者仅使该用例失败，后者整次评测报错、不计分。
- 候选表述：Failure to produce a supported literal fails only that case. If the generated theorem fails kernel checking, the run is treated as an evaluation error and is not scored.

## W02 — retry 判定与“需要重跑”的动作没有区分

- 状态：文案已修正；后文改用 re-evaluation 表达动作，未修改返回状态设计。
- 位置：`rules/evaluation.md:41-43`、`:88-89`、`:95-97`。
- 原文：Verdicts 将 `retry` 定义为计时服务暂不可用、重新排队；`error` 则要求组织者审查。后文又将平台中断和致命评测错误一起写成“requires retry”。
- 问题：后一个 retry 是正式判定状态，还是组织者处理错误后重新评测的动作？读者无法据此判断是否会自动重排、是否必须人工处理。
- 实现核对：`judge/judge.py:2784-2787` 将性能阶段致命错误记为 `error`；`:3186-3198` 区分 `TimingRetry` 与 `InfraError`/未预期异常。本仓库的这些分支不能证明平台会如何自动调度后续重跑。
- 用户解释：后文 retry 表示让用户重试的动作，并不是要返回一个名为 retry 的判定。此处不作为状态机错误处理。
- 建议方向：后文用 rerun/re-evaluation 或“retry the evaluation”明确动作。判定表里已存在的 `retry` 返回及实现不因这一措辞问题而删除；不自行新增自动重排承诺。

## W03 — 第四步保留分题成本政策，取消第五步的额外 correctness 比较

- 状态：规则、README、分题说明及六题配置已更新；通过现有 scorer 的 gate 模式取消额外比较，新增实际题目配置的排名回归测试。官方主机演练仍待完成。
- 位置：`rules/evaluation.md:135-147`；对照 `rules/problem-scoring.md:106-113`、`:165-171`。
- 原文：第 4 步说可互换种子用例的相同部分通过情况保持并列，只有完整计划全通过才比较工作量；第 5 步另起一项说，若题目声明，则比较正确性闭包成本。
- 问题：第 5 步是否也受第 4 步的“全通过”条件限制？独立列出的写法容易让读者以为部分通过时仍比较证明成本。
- 例子：permanent 两份提交都完整通过 R1、R2，R3 全部失败，分数和每组通过数量相同；即使证明成本不同，按现行实现仍然并列。
- 实现核对：`scripts/score.py:869-870` 只在完整计划全通过时启用可互换用例的成本比较；`:1106-1110` 把证明成本的最后比较也放在这个条件内。
- 用户最终决定：第四步按题目比较目标 replay 指令成本，或目标 replay 与 correctness replay 的合计指令成本。前面排名指标及该题第四步选定的成本都相同时即并列；删除第五步，不再额外比较 correctness。这一确认取代此前可能被理解为“所有题目都只比较目标 replay”的表述。
- 第四步公式：令 T = 所有成功目标声明的 replay 指令数中位数之和，C = 完整正确性闭包 replay 指令数的中位数。saw、ca-rule110、sha256 比较 T + C；fib、partition、mertens、primecount、permanent、polydisc 比较 T。C 是 kernel 回放的指令成本，不是编写证明或 elaboration/build 的耗时。
- 保留适用条件：可互换种子用例只有完整计划全通过后才进入成本比较；部分通过且前面排名指标相同的情况仍保持并列。
- 术语确认：第五步的 correctness-closure work 指 `impl_correct` 以及其定义、证明依赖的完整回放指令成本，不是单纯的证明源码长度或编译耗时。
- 联动修改：`evaluation.md` 第 4 步明确按分题政策选择 T 或 T + C，删除第 5 步，将 target work then proof 改为 target work，并同步 Hardcoding and proof cost；`problem-scoring.md` 删除六题末位证明成本比较、保留三题 combined work；README/overview 的计分描述；六题 `proof: last_tiebreak` 配置和有关测试/报告。现有 scorer 支持 `work: curve, proof: gate`，可作为取消六题证明排名项的实现路径，后续修改时再核对。
- 三题处理已确认：`saw`、`ca-rule110`、`sha256` 继续保留 `work: total, proof: include`，不改成只比较目标 replay。保留 combined work 与取消独立的第五步并不冲突。
- 直接证据：三题 `config.json:39` 均明确指定 total/include；`scripts/score.py:1078` 定义 `total_work = correctness_work + curve_work`，`:894-895` 在 total 模式下将其用于排名。对这三题，仍须完整计划全通过才能启用成本比较。
- 历史来源：`git blame` 将三题的 ranking 配置定位到 `5770a18`（2026-08-29，Redesign Stage 1 per-problem scoring）。改版前 `rules/evaluation.md` 的通用公式已经包含 correctness + targets；改版后分题采用两种政策，三题保留相加，另外六题把 correctness 放在最后比较。
- 为什么纳入 correctness：现行 `rules/evaluation.md:123-129` 和改版前对应 Hardcoding and proof cost 段落明确说明，总体目的是让 verified artifact 中的常量、表和证明也承担测量成本。可以把它理解为避免目标 replay 的低成本掩盖一次性的证明/表验证工作，但这是一项评分选择，不是 kernel 的技术要求，也不保证所有表策略都不占优。
- 关于为何选这三题的证据边界：历史提交 `435db5d` 及其版本的 `docs/pre-launch-checklist.md:42-51` 专门讨论 sha256/ca-rule110 的 anchor table：用已证明等价的快速 step 验证中间状态，在 correctness closure 中支付一次遍历成本，再减少各输入 replay 的步数。当时的实例设计与现在不完全相同，不应直接套用旧可利用性结论。没有找到对 saw 或“恰好三题”的明确逐题选择理由，不能把一般动机当成已记录的三题专属理由。
- 范围边界：本次决定取消的是 correctness 成本对排名的额外比较，不自动取消正确性检查、计时回放的完成要求或现有资源上限。

## W04 — 已完成生产验证/已上线的文案与待办清单、日期不一致

- 状态：上线前时态已修正；按用户说明属于提前准备的文案，优先级较低。实际生产验证是否已完成尚未核实。
- 位置：`rules/evaluation.md:184-185`、`rules/overview.md:21-23,110-115`、`docs/pre-launch-checklist.md:3-4,18-23,79-95`。
- 原文：规则正文声称生产测量与容器路径已经在官方硬件验证，overview 声称 2026-09-15 已上线；但当前审核日期为 2026-09-08，清单仍将 PMU 全量测量、容器验证、正式 cohort 演练列为待完成项目。
- 历史依据：`88c87c2` 的提交说明明确这是 launch-day wording，要求上线当天且验证完成后合并；该提交已进入当前 main。
- 注意：清单中关于旧五组难度的说明明确标了 superseded，不能拿旧组别数值当成当前评分规则；上述问题是完成状态没有同步。清单陈旧也不能证明实际验证没有做过。
- 用户说明：当前为 9 月 8 日，文本是暂时提前写好的上线文案；认可过去式不恰当，记录待改。
- 发布边界：`README.md:100-104` 将 overview/evaluation/problem-scoring 链为参赛规则入口，不能把这些规则一概认定为内部文档。上线检查清单属于运维用途，但它是否随仓库公开取决于发布方式。当前 GitHub CLI API 查询未能解析此仓库，不能据此判定仓库公开/私有状态。
- 建议方向：上线前使用 “is scheduled to launch on September 15, 2026” 和 “Production validation must be completed before official evaluation begins.” 等准确措辞；实际完成后再改为带验证日期/记录的完成状态，并同步关闭清单对应项。
- 2026-09-09 QA 关联：反馈的 Live versus pre-launch 对应本项，关联 LKC-QA-011、LKC-QA-133。反馈引用的旧时态已在本地修正，但尚未提交/推送，不能据此认为 sair-server 已收到新规则。后续统一修改时核对 overview、evaluation、README、上线清单的状态一致；真实 PMU/容器验收仍需证据，不能靠改文案将其标记完成。开场具体时刻另记 W11。

## W05 — 临时榜与最终选稿统一按 latest

- 状态：overview/evaluation 已改为统一 latest；平台行为仍需核对，见上线清单第 0 项。
- 位置：`rules/overview.md:73-76` 与 `rules/evaluation.md:113-121`。
- 原文：截止时冻结 newest valid formal submission；临时榜使用 newest formal submission，并明确新版 rejected 也替换旧版 accepted。
- 问题：valid 是成功上传/格式合法、通过正确性检查的 accepted，还是具备计分资格的 scoreable？这三个条件不同。截止前提交仍在排队或遇到基础设施错误时，是否等其评测完成、是否回退，也没有定义。
- 例子：A 先前 accepted 且有分；B 更新但 rejected。临时榜明确按 B 展示，但最终是回退 A 还是仍选 B，取决于未定义的 valid。若 B 是 accepted but unscored，也需明确是否替换 A。
- 用户决定：临时榜和最终选稿统一使用每队每题最新一次正式提交，不再采用 latest valid/latest accepted/latest scoreable。
- 文档修改位置：将 `overview.md:74-76` 的 newest valid formal submission 改为 latest formal submission recorded by the platform before the deadline；将 every accepted submission is a new immutable record 改为每次正式提交均为新的不可变记录，避免 accepted 与成功上传混淆；`evaluation.md:113-121` 保留新 rejected 替换旧 accepted 的临时榜规则，并明确最终选稿采用同一 latest 原则。
- 拟定处理含义：按平台记录的正式提交时间选稿，而非完成评测时间。最新提交 rejected 或 accepted-but-unscored 时，不回退旧稿；截止时仍在排队/评测或遇到基础设施错误，也保留该最新提交，按已有重跑规则处理同一提交。
- 候选正文：Each formal submission is stored as a new immutable record. At the cutoff, the platform selects each team's latest formal submission for each problem, based on the time it was recorded by the platform before the deadline. This selection does not fall back to an older submission if the latest submission is rejected or unscored. Pending evaluation or infrastructure retries apply to the selected submission and do not change that selection.
- 平台联动：这些是选稿语义；本仓库未找到完整的平台选稿实现，后续实施时需对照平台行为，不能从 judge 的单条 verdict 保存逻辑推断已实现。
- 2026-09-09 QA 关联：LKC-QA-050/077/090 仍按旧文案解释为最终 latest valid；LKC-QA-059/089 区分临时 latest 与最终 latest valid。这与用户本轮已确认的统一 latest 不一致，反馈不自动取代该决定。LKC 需发布统一后的 overview/evaluation，供平台再对齐；本记录不声称已经修改 sair-server。临时榜的“最新提交的终态”也不应被改读为“按评测完成时间挑选最新终态”。

## W06 — R2 的 kernel 可归约要求与值生成失败的描述混淆

- 状态：文案已修正；区分值生成失败与确认违反 R2，与 W01 一并落实。
- 位置：`rules/overview.md:85-88`、`rules/evaluation.md:40,78-81`。
- 原文：R2 要求 impl 对每个输入都能由 kernel 归约为输出常量，违反比赛规则应 rejected；evaluation 则把“impl does not reduce to an integer literal”列为只失败一个用例、整次仍可计分的情况。
- 必须区分：elaborator 的值生成过程未能得到常量，不等价于已证实 impl 在 kernel 中不可归约；超时或资源不足也不证明函数根本不可归约。
- 实现核对：`judge/judge.py:1667-1695` 用 elaborator-side `Meta.whnf` 生成候选值；`:2667-2669` 将该阶段报错记为单用例失败。这里只核对分类，不声称已经复现某份违反 R2 的提交被接受。
- 建议方向：将 evaluation 改为“the value-generation step fails to produce a supported literal”，避免直接断言 impl 不可归约；另明确若确认违反 R2 应如何处理。若实际政策允许非归约输入只丢用例分，就需同步调整 R2，而不是同时保留相反的表述。

## W07 — 构建检查并不保证任一性能用例超限即失败

- 状态：用户确认后已修改 README/Dockerfile 注释，按实际回归检查条件描述；未改 harness 行为。
- 位置：`README.md:221-224`、`Dockerfile:96-99`；对照 `scripts/run_harness.py:148-182` 和 `tests/harness_manifest.json`。
- 原文：构建检查保留配置限制，“if even one case exceeds its limit, the build fails”。
- 实现：baseline 清单项仅要求 accepted，不要求 scored。harness 检查 correctness_timing 存在以及每个输入有记录，但不要求 baseline 的目标 replay 成功。带 `scored: true` 的三个优化示例也只要求可计分及最少成功用例数，默认不是全部成功。
- 验证：用既有 `tests/test_scoring.py` 的 grouped_verdict fixture 构造完整、accepted、四个性能用例均 timeout 的 baseline 判定；在临时目录 mock 掉 judge 子进程，调用实际 `run_harness.run_case`，返回 `(True, 'accepted')`。这是对 harness 接受逻辑的隔离验证，没有运行 Lean，没有改变脚本或规则，没有证明某个真实 baseline 当前会超时。
- 影响：构建成功只能证明清单声明的要求得到满足，不能推出所有性能用例都在限制内完成。可故意很慢但正确的 baseline 通过回归检查，本身不必是错误；错误在文案承诺了更强的保证。
- 术语澄清：本项“性能用例”指某份 Submission 在一个具体输入 n 上的检查（可能包含多次 replay）；harness 的 case 则是一份示例 Submission 的回归检查项，两者不应混称。“超限”是某个输入的准备或 replay 阶段超过配置的时间/内存限制。“构建失败”是制作 judge 的 Docker 镜像时，构建内的回归脚本返回失败，从而中止本次镜像构建；它不是选手源文件编译失败的同义词。
- 解释示例：一个 baseline 正确性通过、所有输入都有判定记录，但较难输入 replay 超时。按当前 manifest/harness，它可以满足预期 accepted 并通过回归检查，镜像构建继续。这与 README 若指“任一性能输入超限则中止镜像构建”的承诺不同。
- 建议方向：文案按真实语义写“检查预期判定、测量记录结构及清单声明的最低性能覆盖要求”。如果实际需要任一用例超限即失败，应另设明确的严格检查模式及对应清单，不能只改注释。

## W08 — 取消统一 4 GiB，改为各题独立、可调整的内存政策

- 状态：分题内存政策文案已落实；具体数值、配置和资源执行逻辑仍待完成，见上线清单第 0 项。未自行指定内存值。
- 2026-09-09 QA 关联：反馈中的 8 GiB/4 GiB 文档混杂继续归本项及 W13；最新决定是分题限额，不是将所有说明统一恢复成 4 GiB 或 8 GiB。规则修改、旧记录归档、实际资源执行同步须分别核对。
- 用户决定：取消所有题目统一的 4 GiB 限制，改为每道题独立的内存约束，比赛过程中可调整。这里的题目指 fib、saw 等 problem，不是为每个隐藏输入随意选择上限；也不是取消全部内存限制。
- 新文案方向：Each problem has its own published memory limit. The organizers may revise these limits during the competition. The applicable limit is fixed for each evaluation cohort and recorded in its evaluation policy.
- 与现有版本规则衔接：`evaluation.md:154-164` 已将资源政策纳入 cohort。建议同一题同一比较批次使用相同上限；调整该题内存政策后启用新的 cohort 并重评该题的比较集合，避免将不同资源条件的成绩混排。此处是保持既有公平比较/版本契约的修改方案，不新增具体内存值。
- 配置及实现联动：为各题提供内存上限的权威配置来源；同步规则正文/分题表/README/pipeline 配置。wrapper 应读取并施加该题上限，而非 `run_isolated.sh:211` 强制 `4g`；scorer 的 `scripts/score.py:611` 应校验该题封存的政策，不能继续只接受 `4g`；judge 的 OOM 归因 `judge/judge.py:1145`、资源报告、错误文案及非官方远程 replay 请求也需绑定实际题目上限，不再使用统一 4096 MiB 常量。相关契约测试需同步。
- 原 W08 的剩余含义：即使改为分题限额，镜像构建回归检查也不能自动宣称已经验证了这些正式限额。下面保留旧实现核对，作为构建验证范围的依据；不是要求继续维持 4 GiB。
- 位置：`README.md:214-224`、`Dockerfile:96-104,124-129`；对照 `pipeline/config.json` sandbox.note、`scripts/run_isolated.sh:294-298`、`judge/judge.py:1030-1038,1137-1146`。
- 原文：README 声称构建检查保留 judge 的资源限制，Dockerfile 注释进一步明确说保留 memory limits。
- 实现：Dockerfile 使用 `TIMING_METRIC=wall_time SANDBOX_MODE=none python3 scripts/run_harness.py ...`，harness 直接启动 judge；未经过施加 `--memory 4g --memory-swap 4g` 的正式运行 wrapper，也没有另设每个 worker/评测任务的等价内存限制。judge 的子进程设置只调整 stack rlimit，并不施加 4 GiB 地址空间/内存上限。仓库 CI 的 docker build 命令也没有建立等价的逐任务 4 GiB envelope。
- 证据边界：构建环境仍可能受宿主机、Docker VM 或整个构建 cgroup 的总内存约束；不能称其完全没有内存限制。但共享的构建总预算不等于每份提交的正式 4 GiB job envelope。此发现不表示正式 run_isolated.sh 路径缺少内存限制。
- 影响：在更大构建预算下成功，不足以证明同一任务可以在正式 4 GiB 内完成。README 自己列出的单例峰值 2.3–4.9 GiB 也提醒读者，两处谈论的资源范围需要明确区分。
- 构建文案建议：把构建阶段描述为开发模式回归检查，各题实际内存限额的通过与失败行为由镜像构建后的 wrapper 容器验证来确认；若希望构建检查本身具有同等资源保证，需先落实对应的分题限额再作此承诺。

## 本轮附带的轻微措辞备注

- `README.md:209` 的 `--quick --jobs 2` 注释可明确为“与镜像构建相同的 worker 数”。它的默认每组用例上限为 1、计时/准备上限为 30 秒，而 Dockerfile 另传 `--count 2 --timeout 120`。这里可能只是指并发数相同，不作为新的明确冲突计数。

## W09 — 临时榜使用隐藏抽样输入，不公开运营频率或承诺公开 seed

- 状态：用户已明确不公开临时榜的具体轮换安排、不承担参考输入/seed 的公开承诺；文案已修改。
- 位置：原 `rules/evaluation.md:100-125`、`rules/problem-scoring.md:13-16`。
- 原文：每日临时榜使用 separate hidden reference cohort；正式结果段落说明正式 cohort 关闭后公开 seed/plan，其他段落又概括说输入在 cohort 关闭后公开。
- 未明确之处：参考 cohort 是提交窗口内固定使用一批输入，还是每日/定期轮换；参考 cohort 的关闭条件是什么，是否在关闭时公开 seed/plan，还是所有参考批次统一留到提交窗口或最终评测结束后公开。
- 影响：若轮换，同一份未修改的提交也可能因测试输入改变而得到不同分数；若固定，可比较跨日变化，但需要明确何时退休及公开。正式榜的 seed 公开承诺不应被读成每个临时日榜都立即公开。
- 用户决定：运营轮换安排留在内部流程，不写入仓库文案；临时榜输入保持隐藏，对外仅说明按题目政策抽样且组织者可更新。不承诺每次评测重新抽样，也不承诺公开参考输入或 seed。
- 已修改：evaluation 的临时榜段落与 Hardcoding 段落、problem-scoring 的 seed/plan 公开句、README 的公开说明、prelaunch 的 results/benchmark 公开范围。公开承诺明确限定最终正式评测，不再泛化到临时参考评测。本轮上下文为临时榜，不据此删除既有最终正式评测公开承诺。
- 此仓库没有完整平台调度实现；本文不记录具体内部轮换周期，也不声称已修改线上调度。

## W10 — 拟合原始输入编号，不一定能描述实际规模增长

- 状态：本次 PR 删除 evaluation 的旧诊断介绍；未改变历史报告的拟合实现。
- 位置：`rules/evaluation.md:185-187`；`scripts/score.py:654-670,1056,1071-1072`。
- 文案称 `log cost ≈ α log n + β` 的拟合值有助于描述 scaling behavior。评分器直接用 performance plan 的原始 `n` 拟合，没有按题目解码规模。
- 例如 `sha256` 的输入为 `(steps << 32) | seed`：同为 4 步、不同 seed 的两个输入拥有不同的 `n`，实际链长却相同。`permanent`、`saw`、`ca-rule110` 也使用打包输入。因此不能普遍把这个拟合的 α 解读为针对实际规模的增长指数或算法复杂度。
- 影响有限：α/β 不参与排名；当前 v2 分组榜单也不展示它们，仅旧格式榜单展示（`scripts/score.py:1321-1327,1359`）。这属于诊断说明不准确，不是新的计分矛盾。
- 建议：从当前比赛规则中删去这段旧诊断介绍；若保留，则明确它只是对原始输入编码的描述性拟合，未必反映实际规模增长。未来要展示规模诊断，应另按题目定义规模轴，不能只靠改文案宣称已实现。

## W11 — 官方开场日期缺少具体时刻和时区

- 2026-09-09 更新：暂定 9 月 15 日 22:00 PT（9 月 16 日 05:00 UTC），可能调整；待同步规则和平台。以下保留原 PR 的处理记录。
- 状态：overview/prelaunch 已明确开场具体时刻及其时区待公布；未自行指定数值。
- QA 关联：LKC-QA-009 的开场时间缺项；LKC-QA-011/016 已撤销 RULE 未规定的本地 12:00 UTC 假设。
- 位置：`rules/overview.md` 顶部日期表、Submission 和 Status；`rules/prelaunch.md` 的 Key Dates、Official Repository & Playground。
- 现状：官方开场只有 September 15, 2026，未写时区或时刻；正式提交系统和 SAIR Playground 都以 official launch 为开放节点。提交截止时间已明确为 November 20, 2026, 23:59 AoE (UTC−12)，不属于缺失项。
- 影响：平台无法仅凭该日期确定开放的唯一瞬间，也不应自行补 12:00 UTC 或推导 Playground 可以提前开放。
- 拟改：在一处明确官方开场时刻与时区，其他页面引用同一安排；未定时先明确“具体时刻待公布”，不编造默认时刻。保持 Playground 从官方开场开放的既有规则，生产验收状态继续由 W04 跟踪。
- 待定：用户后续确定开场时刻/时区；这轮不要求立即决定，不增加新的提前开放政策。

## W12 — 最终评测和结果公布缺少日程或明确的待定状态

- 2026-09-09 更新：已确定日榜按 UTC 日末分界，并显示生成时间；最终评测窗口和结果发布时间仍未确定，不能将日榜分界作为最终公布时间。
- 状态：overview/prelaunch/evaluation 已明确评测窗口和结果公布安排待公布，不承诺固定耗时或未经确定的日期。
- QA 关联：LKC-QA-009 中 evaluation period 和 final publication time 缺项。
- 位置：`rules/evaluation.md` 的最终正式 cohort、评测结束后公开及临时榜过渡段落；`rules/overview.md` 日期表；`rules/prelaunch.md` 的 Key Dates。
- 现状：只规定截止后批量进行最终评测、最终 cohort 关闭后公布结果及数据，并允许临时榜在等待期间保留。这说明了先后顺序，没有给出评测窗口或最终公布的具体日程。
- 影响：QA 可以回答流程，但无法从 RULE 得到具体评测日期、持续时间或结果公布时间；这属于信息缺项，不是已有日期互相矛盾。
- 拟改：日程确定后统一列出评测窗口及最终结果公布安排，需精确到时刻的安排同时注明时区；尚未确定则明确标记“待公布”，避免平台自行补日期或固定时长。保留现有截止后评测、完成后公布的流程。
- 待定：评测窗口和结果公布安排，是否采用确定日期或待公布说明；不据此扩大 W09 已限定的最终正式数据公开范围，也不新增临时参考输入/seed 的公开承诺。

## W13 — 上线清单的历史参数仍混在当前验收要求中

- 状态：旧五组、Rule 110、总耗时、4 维 permanent 说明已归档至 `docs/history/prelaunch-calibration-2026-09-07.md`；当前清单已重写为按现行政策验收，关联 W04/W08。
- 位置：`docs/pre-launch-checklist.md` 第 1 节 Official PMU evaluation sweep、第 5 节 ca-rule110 orbit structure、第 7 节 Operational notes；对照 `rules/problem-scoring.md` 当前三组表格及 W08 分题内存政策。
- 现状：清单有 Superseded 提示，但正文仍以 “Also measure ...” 引入 R1–R5、H5、S4/S5、M5、Q5 的旧范围、限时、分值及测量结论；历史说明中还有 8 GiB cap，旧开发测量段使用 4 GiB envelope。
- 问题边界：第 1 节旧数据已有 Superseded 提示，不能据此宣称当前规则仍有五组或 8 GiB 上限；但它们继续嵌在当前待完成事项中，读者仍需判断哪些验收要求有效。第 5/7 节的旧内容则没有单独说明已过时，清单不能直接指导现行三组政策的验证。
- 后续核对 A：第 5 节（当前行 129–146）仍以 C5 = 131,072 步、C4/C5 = 26 + 36 分为依据，将循环跳跃问题列为首次封存前必须选方案解决的项目；当前 C1/C2/C3 仅为 2/4/8 步、20/30/50 分。原先“先算几千步，再跳过后续大量步骤”的分析不能直接证明当前 8 步任务有同一问题。应按新规模重新判定该阻塞项是否仍成立，再归档旧分析或重写待办；不能照旧要求改行宽、筛种子或重定价，也不声称循环问题已由本轮验证消除。
- 后续核对 B：第 7 节（当前行 163–167）的 21–27 小时估算使用 permanent 25 个用例、polydisc 10 个用例和最高 900 秒 replay 限时；当前分别为 15、6 个用例，目标 replay 限时为 30/60/120 秒。旧总时长不可直接用于当前调度。保留从 sealed plan 汇总各阶段上限并留余量的原则，后续重算或移除过期数字；本轮没有计算或承诺新的端到端最坏耗时。
- 后续核对 C：第 7 节（当前行 168–170）称 permanent R1 为 4 维、结果仅有 {6, 8, 9}，当前 R1 已是 6 维。旧 4 维实例的说明应归档，不能仅把数字 4 改成 6 后沿用结果集合；若要保留现行 R1 的结论，需要重新验证。
- 拟改：将旧五组的测量数据、资源假设和结论移到明确的历史说明，保留日期及适用版本；当前清单只引用各题现行三组配置、计分规则和适用的分题内存政策，避免复制一套容易过期的参数。
- 保留必要检查：官方 PMU 全量测量、真实容器隔离、资源失败归因、各组准备成本及可执行性仍需按现行政策验收；没有新测量证据时，不把旧结论当作当前结果，也不将未完成检查标为完成。W08 的具体内存值与实现同步仍是独立待办。
- 完成标准：清单的当前待办不再要求验证已退役的组别或沿用旧限额；历史证据可追溯；当前规则、待实施政策和实际验收状态清楚区分。

## 此前 QA 反馈补记范围（历史）

- 本次只补充 W04/W05/W08 的 QA 对应关系，并新增 W11–W13；未据此修改规则正文、上线清单或 sair-server，也未提交/推送。
- 当时 W10 仍待讨论；本次 PR 的最终处理见顶部状态表。保留用户已确认的统一 latest、取消独立第五步及分题内存政策，不因 QA 引用了旧文档而回退这些决定。

## 前期文案修改验证（历史）

- `git diff --check` 通过。
- `python3 -m unittest discover -s tests -p test_scoring_contract_docs.py`：9 项通过，核对题目表格、用例数、里程碑、限时和工具链一致性；不表示新评分/内存执行政策已经实现。
- `python3 -m unittest discover -s tests -p test_harness_manifest.py`：10 项通过，核对示例清单及构建参数相关检查。
- 本轮没有运行完整 Lean harness 或 Docker 构建；执行逻辑未改，验证范围为文档及相关静态契约。

## 本次 PR 验证

- `python3 -m unittest discover -s tests -p 'test_*.py'`：193 项，192 项通过，1 项因当前 Python 未安装可选 SymPy 而跳过。新增测试直接加载九题配置，验证六题目标成本相同即并列、三题合计成本排序，以及合计成本相同且 correctness 成本不同时仍并列。
- `python3 scripts/run_harness.py --quick --jobs 2`：16/16 个 manifest 示例通过，包括预期 rejected 的示例；这是缩短计划、使用本地 wall-time 的快速回归，不是全部正式性能用例通过的证明。
- 本地 Markdown 链接目标检查及 `git diff --cached --check` 通过。
- 本机未执行官方 Linux PMU 验收或 Docker 隔离验收；当前 Python 的快速检查不能替代上线清单中的生产验证。

---

# 第二轮文案审核追加（2026-09-09）

审核基线：`codex/reconcile-stage1-rules` / `491cb77`（W01–W13 修订之后）；原始查找基线为 `main` / `a66ecf6`。
本节行号以 `491cb77` 为准；引用的代码行号在该提交与 `main` 相同（本轮未改 `judge/judge.py`、`scripts/setup.sh`、`scripts/run_isolated.sh`）。
方法：七个视角并行查找得到 126 条候选，合并为 91 条，每条由独立复核代理按文件逐行反驳（默认判不成立）并单独评定影响，最后再做一轮完整性补查。核实成立 72 条，不成立 29 条，其中 6 条因 `491cb77` 已改掉原文而失效。
本节只记录 W01–W13 未覆盖的部分。与已处理项重叠的发现不重复列出；`K2`（overview 的 "count toward the score"）已由 W03 在 `rules/overview.md:65-68` 解决，不再单列。

## 本轮的处理状态

| 事项 | 类别 | 需要的动作 |
|---|---|---|
| W14 | 实现与规则冲突 | 统一 oracle 与 kernel 的可归约口径，或把 oracle 约束写入规则 |
| W15 | W08 后续 | 定出各题内存数值并同步 wrapper/judge/scorer；确认 permanent R3 等顶档可行 |
| W16–W18 | 赛制设计 | 与共同组织者确认里程碑、分题定价与种子数量是否符合预期 |
| W19 | 文案与实现不符 | 按实际抽样形状改写 geometric range 说明 |
| W20–W25 | 参赛者信息缺项 | 组织者决定后补写（配额、提交结构、Playground、资格、公开与许可、联系方式与回报） |
| W26–W29 | 术语与契约描述 | 统一术语，补齐 retry、计时环境、cohort 封存范围与工具链 pin 的说明 |
| W30–W31 | 状态与上手 | 同步 README 与上线清单的状态；补 Quick start 前置条件 |
| 细项表 | 编辑与陈旧 | 可在一次文案提交中一并处理 |

## W14 — 规则允许 well-founded 递归，但 elaborator 取值步骤按默认透明度必然失败

- 2026-09-09 更新：已确认改用官方独立参考程序或预计算表获取标准答案，不再依赖选手实现取值；实现待完成。下文二选一建议已被此决定替代，复现依据保留。
- 状态：未处理；需要在实现与规则之间二选一。这是本轮唯一一条被实测确认的规则与实现直接冲突。
- 位置：`rules/overview.md:96-99`（R2）、`README.md:113`、`rules/evaluation.md:26-29,80-83`；实现 `judge/judge.py:1678-1695`。
- 原文：R2 允许 well-founded recursion，条件是结果仍可由 kernel 归约；README 写 "well-founded recursion is also permitted"。evaluation 只说值生成是 elaborator-side、失败仅丢该用例。
- 实现核对：oracle 为 `judge/judge.py:1684` 的 `whnf (mkApp (mkConst ``Submission.impl) (mkNatLit __N__))`，按默认透明度求值，未使用 `withTransparency .all` 或 `Kernel.whnf`；非字面量写出 `NONLIT`。Lean v4.33.1 对经 well-founded 编译的定义默认施加 `@[irreducible]`。
- 复核实测：在仓库 pinned 工具链（`lean-toolchain` = `leanprover/lean4:v4.33.1`，于 `problems/fib` 用 `lake env lean`）对一个带 `termination_by` 的定义验证：默认透明度 `whnf` 返回未归约的应用（oracle 会写 `NONLIT`），`withTransparency .all` 与 `Kernel.whnf` 均返回字面量，`Lean.addDecl` 接受 judge 形式的 `Eq.refl` 定理。
- 影响：一份内核确实可归约、符合 R2 字面要求的 WF 提交，会在每个输入上取值失败并得 0 分；规则没有任何提示，选手无法据此推出需要 `unseal` 或 `@[semireducible]`。这与 W06 不同：W06 是措辞分类问题，本项是被明确允许的写法在实现上必然失败。
- 建议方向（二选一，不要同时保留现状）：(a) 让 oracle 与内核口径一致，`judge.py:1684` 改用 `withTransparency .all` 或 `Kernel.whnf`；(b) 把 oracle 的可归约性要求写进规则，说明默认透明度不展开 `@[irreducible]`，WF 定义须自行解封。
- 边界：只验证了 oracle 与内核在 WF 定义上的差异，未逐题检查现有示例（示例提交均为结构递归，不受影响）。

## W15 — 分题内存限额未定值时，顶档与现有硬编码 4 GiB 的关系仍未解决

- 状态：文案层面已由 W08 处理；数值与实现未定，本项记录必须一并确认的具体约束。上线清单第 0 项已列，此处补充判定依据。
- 位置：`rules/evaluation.md:58,86-89`、`rules/problem-scoring.md:39-43`、`README.md:325`；实现 `scripts/run_isolated.sh:211`、`judge/judge.py:1145`、`pipeline/config.json:45`。
- 现状：规则改为"每题独立限额、数值待公布"，但 `run_isolated.sh:211` 仍以 `[[ "$MEMORY" == "4g" ]]` 强制官方运行使用 4 GiB，`judge.py:1145` 的 OOM 归因同样比对 `"4g"`，`pipeline/config.json:45` 仍为 `memory_mb: 4096`。
- 判定依据：`046f8da`（已被 `b768195` revert）的提交说明记录 CI 实测最重用例 2.3–4.9 GiB，其中 permanent 16×16 为 4.9 GiB，并明确写"基线在 permanent R3 会被杀掉"。`problems/permanent/config.json` 的 R3 仍为 16 维、5 个用例、50 分。`README.md:223-224` 也仍写"heaviest cases peak at 2.3–4.9 GiB"。
- 影响：若 permanent 的数值最终定在 4 GiB 或以下，该题 R3 的 50 分在基线上就不可得，"基线满分"校准不成立；若定在 5 GiB 以上，则需同步放开三处硬编码。数值不能只在文案上标注待定。
- 边界：4.9 GiB 是在无 cgroup 限制的镜像构建回归中测得的整机峰值，不是在 `--memory 4g` 下的实际 OOM 观测；结论方向明确，但仍需按 W08 的正式 wrapper 复测确认。
- 建议方向：在 PMU 全量测量时对每题基线取峰值，据此给出各题数值；同一提交内改 `run_isolated.sh`、`judge.py` 归因、`pipeline/config.json` 与分题表；若某题数值低于其基线峰值，应同时下调该题顶档规模。

## W16 — 基线可能在每题拿满 100 分，里程碑与排名前三步随之失效

- 2026-09-09 更新：赛制方向已确认；全部输入通过得 100 分，任一失败得 0 分并视为无限成本，满分者按指令成本排名。基线满分不再作为待修缺陷；旧的部分分与组别排序待整体替换。
- 状态：未处理；属于赛制取向，需要与共同组织者确认。
- 位置：`rules/problem-scoring.md` 各题表；`rules/evaluation.md:150-158`（排名 1–4 步）；`README.md:177-179`。
- 依据：三组阶梯按基线峰值内存分档（约 0.03 / 0.3 / 3 GiB，见归档的转换说明）；`results/` 下本地开发记录显示 fib、partition、mertens、primecount 的基线目标 replay 均在数秒内完成，远低于 30/60/120 秒限时。
- 影响：若任何正确提交都能拿满 100 分，则排名第 1 步（总分）、第 2 步（难组分数）、第 3 步（用例剖面）对所有人并列，实际只剩第 4 步的测量成本比较。分组里程碑成为形式，"难度阶梯"的对外叙事与实际排名机制不一致。
- 附带：直接范围题的顶档规模（mertens 300–500、primecount 600–1,000、partition 32–36）相对其二次/指数规格仍在很小的量级，同样指向这一点。
- 边界：这是基于本地 wall-time 记录的推断，不是官方 PMU 环境的结论；正式测量后若基线在顶档确实失败，本项自动消解。
- 建议方向：PMU 全量测量时同时记录基线在每组的通过情况。若基线确实满分，明确对外说明"分数用于区分正确性达成度、名次由测量成本决定"，或上调顶档规模使基线不能通吃。

## W17 — polydisc 的三个区间成本平坦，却按 20/30/50 递增定价，且区间数与 Spec 不一致

- 2026-09-09 更新：取消部分分后，无须重新决定三个组如何分配 20/30/50 分。规格支持五级而正式计划采样三级本身不矛盾，可补充映射说明。
- 状态：未处理。
- 位置：`rules/problem-scoring.md:170-178`、`README.md:137`；对照 `problems/polydisc/Spec.lean:6-7`、`problems/polydisc/config.json`。
- 依据：`046f8da` 调整阶梯时明确将 polydisc 排除在外，理由是"其成本在输入范围内是平的"；但该题仍按 D1/D3/D5 = 20/30/50 定价，并适用"难组分数优先"的通用排名规则。
- 附带两处描述问题：`Spec.lean:6` 说 "Five coefficient-scale bands"、`kbitsOf` 定义五级宽度，而 `README.md:137` 说 "three coefficient-scale bands"，且 `rules/problem-scoring.md:174` 用 "the retained bands D1, D3, and D5" 指代读者看不到的 D2/D4，未说明 Stage 1 只取第 0/2/4 级、编号为何不连续。
- 影响：若三档实际难度相近，递增分值与"难组优先"的比较顺序就不反映难度；描述不一致也会让选手误以为存在未公开的区间。
- 建议方向：确认三档是否确有难度梯度；若无，改为等分或重新选择区间。同时在分题说明中写明 Spec 的五级宽度与 Stage 1 采样的三级对应关系，去掉 "retained" 这一指向历史的措辞。

## W18 — 每组仅两个隐藏种子，顶档结果受种子难度差异影响

- 状态：未处理；上线清单第 5 项已要求在 PMU 阶段复查生成器，本项给出需要复查的具体量级。
- 位置：`rules/problem-scoring.md:126-141`（saw）、`:142-155`（ca-rule110）、`:156-169`（sha256）、`:170-178`（polydisc）。
- 依据：saw 的规格按约 1/11 密度布置障碍，长度 8 的合法走法计数在不同种子间约 850–5,700，10 与 90 分位之间约 2–3 倍；S3 为 2/2 全通过才给 50 分，且以 S1、S2 为前置。
- 影响：在接近限时的提交上，顶档的成败可能取决于抽到的种子难度而非算法优劣；每组仅 2 个种子时这一方差无法被平均掉。
- 边界：本项是对生成器输出分布的统计，不是对某份提交实际超时的观测；实际影响取决于选手成绩相对限时的位置。
- 建议方向：在 PMU 测量时记录同组不同种子的成本离散度；若离散度大，增加每组种子数，或对全或无的顶档改为按通过数给分。

## W19 — geometric range 抽样说明与实现的取值形状不符

- 状态：未处理；改文案即可，不需改实现。
- 位置：`rules/problem-scoring.md:57-58`；实现 `judge/judge.py:494-501`、`:420-429`。
- 原文：称为"在公布的闭区间内选取互不相同、严格递增的整数，带确定性的 15% 种子抖动"。
- 实现核对：`count = 2`（fib、partition、mertens、primecount 的每一组都是 2）时，`judge.py:498-499` 把第 0 个用例标为 `lower`、第 1 个标为 `upper`；`_group_jitter`（`:421-428`）对 `lower` 只向上抖动、对 `upper` 只向下抖动，幅度不超过 15%。区间中部不可能被取到，"geometric" 的等比间隔在两点时不起作用。未设 seed 的本地运行返回区间端点本身。
- 影响：例如 fib F1（5,000–10,000）实际只会取到约 5,000–5,750 与 8,500–10,000 两段，选手若按"区间内任意值"准备，对成本上界的估计会偏低。partition 因区间窄，15% 带宽覆盖整个区间，不受影响。
- 建议方向：改写为"一个取靠近区间下界、一个取靠近区间上界，各自向内做不超过 15% 的确定性抖动；未设 seed 的本地运行使用区间端点"，并相应调整第 58-59 行关于两用例排序的说明。

## W20 — 每日提交配额的适用范围与计入判定未定义

- 2026-09-09 更新：Standard 每日 2 次、Light 每日 5 次已确认；按队/按题的计数范围、与正式提交的额度关系及失败退额仍待明确。规则由主办方确定后由平台落实，不能反向以实现代替政策决定。
- 状态：未处理；需要先确认平台实现。
- 位置：`rules/overview.md:82-87`。
- 原文："up to 10 per team per UTC day"，紧接的截止冻结句则明确写 "for each team and problem"。
- 未明确之处：其一，10 次是全部九题合计还是每题各 10 次（10 与 90 的差别）；相邻句子一个不带分题限定、一个带，容易被读成后者。其二，被拒绝的提交是否计入配额；`error`/`retry` 是否计入。
- 实现核对：`pipeline/config.json` 与 `judge/judge.py` 均无提交计数逻辑，配额由平台侧实现，仓库内无可据以判定的实现。
- 建议方向：按平台实际实现补上限定语，并明确"每次正式提交无论判定结果均计入""基础设施判定不计入"之类的规则。此项与 W05 的 latest 选稿规则相互影响，宜在同一处说明。

## W21 — 提交文件的结构要求不完整，且未被 judge 检查

- 状态：未处理；需要先决定是否执行。
- 位置：`rules/overview.md:74-76`、`README.md:83-95`。
- 原文：要求提交恰好一个 `Submission.lean`，`impl`、`impl_correct` 及每个辅助定义与引理都在 `namespace Submission` 内。
- 缺项一：每个模板与示例的首行都是 `import Spec`，而规则与 README 的示例片段都没有这一行，也没有任何文档说明允许哪些 import。R2 的 "core Lean without Mathlib" 未展开为具体集合（事实上锁定工作区没有 Lake 依赖，只有 pinned 工具链的 `Init`/`Std`/`Lean` 能解析）。
- 缺项二：judge 不做命名空间检查，只校验文件数、是否为常规文件、大小；`Solution.lean` 只引用 `Submission.impl` 与 `Submission.impl_correct`。仓库自身的 `examples/submissions/ca-rule110/bitpacked/Submission.lean` 就有 7 个顶层定理与 `def M` 在命名空间之外，而 `tests/harness_manifest.json` 期望它 accepted 且计分。
- 影响：一条写成硬性要求、实际不执行且被自家示例违反的规则，选手无法判断其约束力。
- 建议方向：补写 `import Spec` 与允许的 import 集合；命名空间要求改为建议（说明实际约束是构建通过、R2 与 R4），或在 judge 中加入检查并同步修正示例。

## W22 — Playground 与提交后可见的反馈都未描述

- 2026-09-09 更新：模式次数见 W20；日榜必须显示生成时间。模式行为、具体反馈范围仍需补写，不因次数确认而整体关闭本项。
- 状态：未处理。
- 位置：`rules/prelaunch.md:85-88`、`rules/overview.md:32-33`、`rules/evaluation.md:125-138`。
- 现状：SAIR Playground 只被列为"随官方开场开放"，全文没有说明它是否走同一 judge、是否给出判定、是否计入 W20 的配额。"formal submission" 中 "formal" 所对应的非正式路径也从未指明。
- 另一处缺项：没有任何文档说明选手提交后能看到什么——拒绝原因文本、分组通过数与得分、超时或内存判定的分类，还是只有每日临时榜上的最终判定。
- 影响：选手无法判断该用 Playground 还是正式提交来试错，也无法预期调试信息的粒度；这直接影响 W20 配额的使用策略。
- 建议方向：用一段说明 Playground 的定位（是否走 judge、是否出判定、是否计配额），并列出提交后返回给选手的字段。若平台侧尚未定，标注待公布而不是留空。

## W23 — 参赛资格、团队定义、sponsor 与协作边界未定义

- 2026-09-09 更新：已核对用户指定的 Equational Theories Stage 2；其三条规定与 LKC 相同，未定义 organization 或大学例外。参考原文没有消除该歧义，不能视为已确认大学整体只能一队。
- 状态：未处理；含需要组织者决定的政策项。
- 位置：`rules/prelaunch.md:90-94`、`rules/overview.md:82-87`、`rules/evaluation.md:127-131`。
- 缺项：
  - "Each individual or organization can participate in only one team" 按字面读，一所大学或一家公司只能有一支队；这可能不是本意。
  - "sponsors" 全仓库仅此一处出现，未定义；"in advance" 无明确截止（`70f1fe3` 曾把原来的 "before their first submission" 改成此措辞）。没有名单冻结时点。
  - 反作弊只覆盖 sockpuppet，未说明队间共享代码、在 Zulip 公开讨论解法、复用他人公开提交是否允许。
  - 没有任何回避条款：未说明共同组织者、judge 与 kernel 维护者、持有 `PERF_SEED` 与临时榜参考种子的人员能否参赛。
  - 每日配额与截止冻结按 team 表述，临时榜按 entrant 表述，而 prelaunch 允许个人参赛，三者未打通（个人是否视为一人队没有明说）。
- 建议方向：逐条决定后写入 prelaunch；把 organization 改为对个人的限制，给出名单冻结时点，明确协作与公开讨论的边界，补回避条款，并统一 team/entrant/个人的用词。

## W24 — 选手提交代码的公开范围、许可与平台条款链接未定

- 2026-09-09 更新：已确定比赛期间不公开选手代码、赛后公开；版本范围、许可和正式条款仍待明确。
- 状态：未处理；需要组织者决定后才能定稿。
- 位置：`rules/prelaunch.md:38-44,80-83`、`rules/evaluation.md:120-124`、`README.md:170-173`。
- 原文：承诺最终正式评测的 seed、输入计划、结果与 benchmark 数据以开源许可公开，并说"通过挑战产生的算法与表示"将共同构成可复现、复用的社区贡献。
- 未明确之处：选手的 `Submission.lean` 是否公开、公开全部还是仅上榜提交、采用何种许可（仓库 `LICENSE` 为 Apache-2.0）、选手提交是否即视为授权。另外 "SAIR competition terms" 只链接到平台首页，条款本身没有可引用的地址。
- 影响：涉及选手的著作权与参赛意愿，属于必须在开赛前明确的条款，不宜留待事后解释。
- 建议方向：确定公开范围与许可后写入 prelaunch，并把条款的正式地址补上；措辞需与平台条款一致。

## W25 — 缺少组织者联系方式，也未说明名次的实际回报

- 状态：未处理。
- 位置：`CONTRIBUTING.md:36-38`、`rules/evaluation.md:42-45`、`rules/overview.md` 日期表。
- 现状：CONTRIBUTING 要求发现"能让错误提交被接受"的问题时"直接联系组织者"，但全仓库没有任何邮箱或安全披露渠道；`error` 判定与致命评测错误都写"需要组织者审查"，同样没有联系方式与时限。唯一的对外渠道是 prelaunch 末尾的 Zulip 链接，而它被定位为社区讨论，不适合报告可利用的评分漏洞。
- 另一处缺项：没有任何文档说明榜单名次带来什么——奖金、荣誉、Stage 2 资格，或不带来任何东西。
- 建议方向：补一个安全披露地址（或明确指向平台的私密渠道）与预期响应时限；名次回报若未定，明确标注待公布。

## W26 — 术语未定义与跨文档命名不一致

- 状态：未处理；集中一次改完即可。
- 位置与内容：
  - `rules/evaluation.md:58,94`（"attested"）、`:177,189-195`（"KTP/3"、"local-v2"）：三个词从未展开或解释，读者无法判断其含义与适用范围。
  - `rules/evaluation.md:155-158` 用 "Ordered range samplers" / "Interchangeable seeded samplers"，`rules/problem-scoring.md:30-33` 用 "Direct-range problems" / "Packed and uniformly seeded cases"，`README.md:188` 用 "packed or uniformly seeded groups"，而术语表（`problem-scoring.md:57-62`）定义的是 geometric range / uniform integer / packed。四套叫法指同两类，且从通用规则的措辞看不出 polydisc（uniform integer）属于可互换类。
  - `rules/evaluation.md:172` 的 "Submission name" 在全部文档中没有定义，只存在于实现（`judge.py` 的 `--tag` 或提交目录名，`score.py` 用作显示排序键）；平台提交对应什么名字没有说明。
  - `README.md:151` 的判定流程图列出 "slugs" 校验，该词未定义。
- 建议方向：统一采用术语表的三个抽样器名称，并在排名规则中直接对应 `ranking.profile` 的两个取值；为 attested、KTP/3、local-v2 各加一句解释；说明"submission name"在平台上的对应物，或改写为按接受时间排序。

## W27 — retry 的定义只覆盖非官方路径

- 状态：未处理。
- 位置：`rules/evaluation.md:42`。
- 原文：`retry` 定义为"计时服务暂时不可用，重新排队且不计分"。
- 实现核对：官方评测强制使用容器内本地 PMU 且禁用远程执行器（`judge.py:2340-2341`），而 `TimingRetry` 只在 `_time_remote` 与信号处理中抛出。因此官方运行里唯一可能产生 `retry` 的路径是编排器信号终止（对应上线清单里的外层墙钟上限），而不是定义中写的计时服务不可用。
- 影响：判定表对官方评测给出的是一个在官方路径上不会发生的原因，选手无从理解自己为何看到 `retry`。
- 建议方向：把定义改为"平台在判定完成前中断了评测（例如编排器墙钟上限或节点回收），自动按同一封存计划重排且不计分"，并附注远程执行器不可用只发生在非官方 KTP/3 模式。W02 已把后文的动作性 retry 改为 re-evaluation，本项针对的是判定表本身。

## W28 — 官方计时环境与本地自测口径对选手不可估算

- 状态：未处理。
- 位置：`rules/evaluation.md:48,189-195`、`rules/problem-scoring.md:36-43`、`rules/overview.md:110-111`、`README.md:39-40`。
- 缺项：
  - 官方主机只描述为 "pinned Linux PMU host/executor"，没有任何可据以估算的信息；而各组限时是整进程墙钟，包含未计入指标的解析与依赖预载，选手无法判断 30/60/120 秒对应多少可用计算。
  - 排名按精确的指令数中位数比较，没有公布等价容差或近平局重跑机制，而上线清单自己把"指令计数是否稳定到足以确定性排名"列为待验证项。
  - `scripts/perf_eval.py` 被推荐给选手，但没有任何文档给出它的命令行参数与前置条件。
  - `README.md:39-40` 说内核成本取决于"一组固定的原生 `Nat` 操作"，却没有列出这组操作，尽管实现里已有清单（`judge/judge.py:159-163`）。
- 建议方向：公布主机的关键规格或给出一个参考基线（例如某个示例提交在官方机上的实测值），补 `perf_eval.py` 的用法，把原生 `Nat` 操作列表写进 README，并说明指令数相同或差异在容差内时如何处理。

## W29 — cohort 封存范围与工具链 pin 的描述有缺口

- 状态：未处理；影响运营正确性大于影响选手。
- 位置：`rules/evaluation.md:182-185,196-197`、`README.md:196-198,302-303`。
- 内容一：`judge.py:2234-2235` 把 `problem_bundle_sha256`（题目锁定文件）与 `evaluator_bundle_sha256`（Dockerfile、`judge.py`、`score.py`、`run_isolated.sh`、`setup.sh`、评测配置、timer kernel、comparator patch）一并计入 cohort id，而 evaluation 列举 cohort id 承诺的内容时没有提这两项。由于规则禁止跨 cohort 混排，对这些文件的任何字节级改动（包括只改注释）都会轮换 cohort id 并分叉榜单，文档没有提示这一点；上线清单只警告不要改用例、分值与限时。
- 内容二：comparator 的 pin 写作裸的 `3927ad3`，实际运行的是该修订加上仓库内 `patches/comparator-emit-export.patch`（`scripts/setup.sh:50` 应用，`Dockerfile` 构建时执行）。按文档字面复现会得到与官方不同的二进制。
- 建议方向：在 cohort id 的承诺清单中补上两个 bundle 摘要并提示运营须冻结这些文件；工具链一节写明 comparator 为"该修订 + 仓库内 patch"。

## W30 — README 与上线清单的状态描述已落后于本次修订

- 状态：未处理；`491cb77` 改了规则文件，README 与清单的若干句子未同步。
- 位置与内容：
  - `README.md:319` 仍写"remaining launch blockers are the production PMU sweep and real-container isolation validation"，而清单现已有第 0 项（实现九月九日规则评审）与第 5 项（生成器与工作负载复查），二者都不属于这两类，且未标为非阻塞。
  - `docs/pre-launch-checklist.md:54-55` 写 judge 在"elaborating any submission 之前"预检 `perf stat -e instructions`；实际调用点在 comparator 正确性关与公理复审之后（有意如此，使无 PMU 主机仍能跑通该关），`judge.py:1402` 的 docstring 同样沿用旧措辞。
  - 归档到 `docs/history/prelaunch-calibration-2026-09-07.md:27` 的一条数据其实仍然有效：其中 "sha256 H5 的 512 步在开发机实测约 133 秒、限时 120 秒"，而当前 `H3` 恰好也是 512 步、120 秒限时（`problems/sha256/config.json`）。该数据被整体标注为已退役布局，可能掩盖一个仍然存在的顶档不可达风险。
  - `CONTRIBUTING.md:31-32` 只把 `run_harness.py` 称作 green gate，`README.md:294` 只把 `tests/` 描述为清单，均未提 CI 另外执行的检查。
  - `CONTRIBUTING.md:21-24` 的加题清单只列了 `harness_manifest.json` 与 `problem-scoring.md`，未提九题 id 还硬编码在 `tests/test_scoring_contract_docs.py`（`DOC_SAMPLER_KINDS`、`EXPECTED_PROBLEM_COUNT`）与 `tests/test_problem_policies.py` 中。
  - 对抗性示例只覆盖 `sorry`、自定义公理与 `import Mathlib`；规则声明会拒绝的 `native_decide`、`partial`/`unsafe`、不可归约的 WF `impl`、命名空间外的辅助定义都没有对应的回归用例（与 W14、W21 相关）。
- 建议方向：按清单实际条目改写 README 的阻塞项句子；修正预检措辞与 docstring；把 sha256 的 512 步数据从归档中提出、作为当前顶档的待验证项；补 CONTRIBUTING 的加题清单与 CI 说明；按规则条目补齐对抗性用例。

## W31 — README Quick start 缺前置条件与平台说明

- 状态：未处理。
- 位置：`README.md:213-220`；对照 `scripts/setup.sh:18-19`。
- 现状：Quick start 直接给出 `scripts/setup.sh` 等命令，未说明前置条件与适用平台。按字面执行时，`setup.sh:18` 在缺少 `elan` 时直接报错退出，`:19` 在 macOS 缺 `gtimeout` 时告警（需 `brew install coreutils`），随后还要克隆并 `lake build` comparator 与 lean4export。Windows 下的可用性未提及。
- 影响：这是选手接触仓库的第一段命令，失败点集中且可预先说明。
- 建议方向：在代码块前加一行前置条件（elan；macOS 需 coreutils；首次构建需要网络与若干分钟），并说明支持的平台。

## 编辑与陈旧细项（核实成立，未单列 W）

| 位置 | 问题 | 建议 |
|---|---|---|
| `rules/problem-scoring.md:145-146` | "the old fixed 32-cell short orbit" 指向只存在于 git 历史的设计（`fc4e0fd` 的 `ruleWidth := 32`，`5770a18` 已改为 256） | 删去与旧设计的对比，直接陈述当前构造 |
| `rules/problem-scoring.md:174` | "the retained bands D1, D3, and D5" 暗示存在读者看不到的 D2/D4 | 见 W17，改写为与 Spec 五级的对应说明 |
| `rules/problem-scoring.md:67,78,101,126` | 分题标题的修饰语（scaling frontier、subtask frontier、robust scaling frontier、seeded-obstacle prefix frontier）是五组时代遗留，未定义 | 删除或统一为可理解的短描述 |
| `README.md:34-36` | 开源贡献段插入在内核归约段与其续写之间，导致第 38 行的 "This" 指代断裂 | 将该段移至 Background 末尾 |
| `README.md:179` | "Passing cases reaches that group's milestones and awards points" 主谓不一致，且 "that group's" 无先行词 | 改为 "Cases that pass reach the group's milestones, which award its points" 一类写法 |
| `README.md:137` | 问题表 "Naive spec cost" 列在 polydisc 行填的是算法名而非复杂度，与其余各行不同类 | 补该题的渐近成本，或拆出单独的算法列 |
| `README.md:6-16`、`rules/overview.md:6-16`、`rules/prelaunch.md:6-17` | 共同组织者名单逐字重复三处，仅 prelaunch 带 logo | 保留 prelaunch 一处，其余改为链接 |
| `README.md:222-236` | 面向运维的镜像构建策略段落位于面向选手的 Quick start 内；且是全仓库唯一使用句号后双空格的文本 | 移入 CONTRIBUTING 的 Green gate 一节 |
| `README.md:288-299` | 仓库布局树遗漏 `docs/`、`assets/`、`patches/`、`LICENSE` | 补齐 |
| `rules/prelaunch.md:1` | 文件名与其长期有效的内容（截止日期、注册、团队与费用政策）不符，H1 与 README 逐字相同 | 考虑改名为 `participation.md` 并改写标题 |
| `CONTRIBUTING.md:3`、`Dockerfile:1`、`scripts/setup.sh:2`、`scripts/run_harness.py:2` | 残留已废弃的 "kernel-computation track" 称谓 | 统一改为 Stage 1 |
| `CONTRIBUTING.md:6,26,31,36` | `##` 标题后无空行；New problems 列表前四项以分号结尾、第五项为完整句 | 统一格式 |
| `rules/overview.md:20-21` | 日期表首行为空表头，GitHub 渲染出一行空白 | 补表头或改为列表 |
| `rules/prelaunch.md` 各标题 | 全文用 Title Case 并混用 "&" 与 "and"，与其余文件的句式标题不一致 | 统一 |
| `rules/evaluation.md:94-97`、`rules/problem-scoring.md:174-175` | 硬换行宽度在文件内不一致，个别行超过 110 字符 | 统一重排 |
| `README.md` 全文 | naive / naïve 混用 | 统一 |
| `rules/evaluation.md:69`、`rules/problem-scoring.md:11` | 提到分组可声明 kernel-instruction 限制（实现确实支持），但九题均未声明，文档未说明这一点 | 注明当前无一组声明该限制 |
| `rules/evaluation.md:185` | "accepted but unscored" 未说明在临时榜与最终榜上如何显示（0 分、横线，还是不显示） | 补一句显示规则 |
| `rules/prelaunch.md:87-88` | 称"官方仓库"将随开场在 SAIR 提供，但未说明本 GitHub 仓库是否即该仓库 | 明确二者关系 |
| `README.md:306` 一带 | 未说明规则变更在何处公告、开赛后哪些内容可变 | 补一句变更公告渠道 |

## 本轮核实不成立的项（记录以免重复提出）

| 项 | 复核结论 |
|---|---|
| AoE 截止与 UTC 配额重置构成冲突 | 不成立。截止是单一时刻，配额有明确的 UTC 重置定义，二者不矛盾 |
| `fib` 的 "(tutorial)" 标签是陈旧遗留 | 不成立。初始提交即有，与其满分计分并存是有意设计 |
| mertens/polydisc 返回 `Int` 会导致取值失败 | 不成立。`Meta.whnf` 会继续展开 `Int.ofNat` 分支，oracle 有对应处理 |
| 各文档重复陈述评测契约导致无法判断何者具约束力 | 不成立。README:99-104 已明确各文件的角色分工 |
| 网页端 10 KB 上限与规则的 1 MiB 矛盾 | 仓库内不成立（仓库各处一致为 1 MiB）；属平台侧问题，须另向平台确认 |
| saw / ca-rule110 顶档规模过小的两条具体论证 | 不成立。所引用的耗时数字与 `results/` 的实测记录不符（W16、W18 保留了该方向中可验证的部分） |
| 无总预算加上 retry 重排会导致无限重排 | 不成立。清单本身要求按封存计划计算外层墙钟上限 |
| 规则禁止"利用 judge"与 CONTRIBUTING 鼓励提交作弊样例冲突 | 不成立。后者面向仓库贡献者，前者面向参赛提交，语境可区分 |
| 各文档对 `spec` 的写法与实际声明名（`fibSpec` 等）不符 | 不成立。占位写法在上下文中可理解，未构成实际歧义 |
| 部分陈旧措辞与段落冗长问题 | 已由 `491cb77` 改掉原文，不再适用（共 6 条） |

## 本轮方法与验证

- 查找与复核均在 `codex/reconcile-stage1-rules` / `491cb77` 的工作树上进行；每条发现由独立复核代理逐行核对原文与相关实现，默认判不成立，仅在能引用具体文件行号时才确认。
- W14 的透明度差异经实际运行验证：在 `problems/fib` 下用 `lake env lean`（工具链 v4.33.1）对带 `termination_by` 的定义比较默认 `whnf`、`withTransparency .all`、`Kernel.whnf` 与 `Lean.addDecl` 的行为。
- W15、W19、W29、W30 的实现结论来自对 `judge/judge.py`、`scripts/run_isolated.sh`、`scripts/setup.sh`、`pipeline/config.json`、`problems/*/config.json` 与 `tests/` 的直接核对；本轮未运行 Lean harness、Docker 构建或官方 PMU 测量。
- W16、W18 基于 `results/` 下的本地 wall-time 记录与生成器输出分布，属推断而非官方环境结论，已在各条中标注边界。
- 本节只追加记录，未修改任何规则正文、配置或实现。
