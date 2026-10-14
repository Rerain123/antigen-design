"""Service-owned MCP guidance, shared by initialization and tool discovery.

Clients may omit initialize.instructions from model context, so each tool also
carries its relevant rules. Metadata never replaces backend checks or consent.
"""

GUIDE_VERSION = "t01-client-guide-20261008-v2"
SUBMIT_TOOL = "workflow_submit_sequence"
CHECK_TOOL = "workflow_check"
CONFIRM_TOOL = "workflow_confirm_design"

WORKFLOW_USAGE = (
    "抗原设计入口：收集单条蛋白序列和宿主→提交一次→按用户后续请求查询→"
    "后台按已配置策略自动推进→展示终态报告。新任务的空FIXED分支按预授权继续并保留警告，"
    "不再中途询问；硬失败和预算停止仍由后端执行。N01–N18由后端按门控和条件执行，"
    "模型不逐节点调度，不生成科学参数或结论；跳过、失败、未执行须如实说明。"
    "本入口所需操作由这三个工具提供，无须为提交或查询额外检索Skill。"
    "仅使用客户端实际提供的工具，名称可能带平台前缀。"
)

SUBMIT_USAGE = (
    f"用户明确要求运行且已给出单条明确序列和宿主时，直接调用一次{SUBMIT_TOOL}；"
    "仅在输入缺失、多条序列或边界含糊时追问。protein_sequence按原顺序拼接明确的序列行，"
    "只移除行内空白和换行，不改字母、不补齐、不截断、不把说明文字混入序列；"
    "当前接口接受9–999 aa大写AA20序列，字符和长度由后端校验，"
    "不要逐字符计数、分组复数或反复重写；长度只引用返回的sequence_length。"
    "host_species按用户原文传递，例如用户说猪就传猪，不翻译或追加拉丁名，映射由后端处理。"
    "run_key默认省略；同一序列、宿主和run_key幂等，不为查询进度重新提交或换key。"
    "不得构造结构、位点掩码、数据库参数或设计确认。输入错误按工具返回说明，不能擅自修正序列重试。"
    "拿到job_id才说明已接收并交由后台处理；queued是提交时快照，不表示前方必有其他任务，"
    "不能把queued说成已开始科学计算。简短给出job_id、后端长度、宿主和状态；"
    f"用户稍后可用{CHECK_TOOL}查询，本轮不循环等待。"
)

CHECK_USAGE = (
    f"用户查询进度时，使用本会话明确的job_id调用一次{CHECK_TOOL}；"
    "已有job_id不再向用户索取，多个任务无法确定时才澄清，不能用提交工具代替查询。"
    "运行中转述state、current_nodes和completed_nodes/total_nodes；"
    "completed_nodes含失败和跳过，成功数量看node_counts，节点比例不代表耗时百分比。"
    "active_steps.execution.phase中waiting_worker表示等待Worker，executing表示回执记录执行中，"
    "finalizing表示原生进程停止后收集结果，unknown表示未确认；"
    "父任务running/reconciling不证明原生工具正在计算，回执不是实时CPU采样。"
    "state=controller_error时明确说明控制器异常，引用controller.code，不把它描述为继续计算或正常排队。"
    f"pending_confirmation非空时展示后端warning和prompt，用户明确决定后才调用{CONFIRM_TOOL}。"
    "终态返回{data,type}时直接交由HiMat渲染报告卡，保留primaryAttachmentId和全部附件URL，"
    "不重拼卡片、不调用旧workflow.report；缺项和失败按后端事实说明。"
    "COMPLETED仅表示工程报告交付，不代表合格候选或科学签收；资格按scientific_gate、"
    "usable_for_pipeline和production_status说明。本次查询结束后后台继续运行，无须循环等待。"
)

CONFIRM_USAGE = (
    f"仅当{CHECK_TOOL}返回pending_confirmation时使用{CONFIRM_TOOL}。"
    "先完整转述后端warning和prompt；用户明确同意传decision=true，明确拒绝传false，"
    "未决定时不调用。job_id和confirmation_id逐字取自本次查询，不能猜测。"
    "此工具仅用于仍保留交互策略的历史任务；新任务由后端按预授权策略记录T4决定，模型不代造确认。"
    "确认后沿用原run，重复相同决定幂等，不重跑前段工具；"
    f"确认后状态以工具返回为准，后续进度使用{CHECK_TOOL}，不重新提交。"
)

SERVER_INSTRUCTIONS = "\n\n".join((
    f"T-01工作流使用说明（{GUIDE_VERSION}）。本说明仅描述本服务工具的使用方式。",
    WORKFLOW_USAGE,
    SUBMIT_USAGE,
    CHECK_USAGE,
    CONFIRM_USAGE,
))
