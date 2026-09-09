# 文案审核记录（2026-09-08）

审核基线：`main` / `a66ecf639a48208120eff5fc4c0f30c902173af5`。
按讨论逐项记录，区分明确冲突、歧义和需要确认的政策选择；实现用于核对现状，不自动视为规则权威。
本文是历史问题与决定记录，包含已废弃的原文引用；现行规则以 `rules/` 为准，当前验收待办以 `docs/pre-launch-checklist.md` 为准。
前期文案修订后，2026-09-09 用户要求开 PR。本次同时完成六题排名配置同步；未修改内存执行逻辑或 sair-server。
以下原文行号以审核基线为准，修改后的行号会变化。

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

- 状态：overview/prelaunch 已明确开场具体时刻及其时区待公布；未自行指定数值。
- QA 关联：LKC-QA-009 的开场时间缺项；LKC-QA-011/016 已撤销 RULE 未规定的本地 12:00 UTC 假设。
- 位置：`rules/overview.md` 顶部日期表、Submission 和 Status；`rules/prelaunch.md` 的 Key Dates、Official Repository & Playground。
- 现状：官方开场只有 September 15, 2026，未写时区或时刻；正式提交系统和 SAIR Playground 都以 official launch 为开放节点。提交截止时间已明确为 November 20, 2026, 23:59 AoE (UTC−12)，不属于缺失项。
- 影响：平台无法仅凭该日期确定开放的唯一瞬间，也不应自行补 12:00 UTC 或推导 Playground 可以提前开放。
- 拟改：在一处明确官方开场时刻与时区，其他页面引用同一安排；未定时先明确“具体时刻待公布”，不编造默认时刻。保持 Playground 从官方开场开放的既有规则，生产验收状态继续由 W04 跟踪。
- 待定：用户后续确定开场时刻/时区；这轮不要求立即决定，不增加新的提前开放政策。

## W12 — 最终评测和结果公布缺少日程或明确的待定状态

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
