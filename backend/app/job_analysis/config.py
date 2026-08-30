"""JD Filter 全局配置 —— 换供应商只需修改此文件。"""
import os
from pathlib import Path

# ── API ──
# 支持 OpenAI-compatible API（DeepSeek / 其他供应商）
# 设置环境变量后运行，也可直接修改下方默认值
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://opencode.ai/zen/go/v1")

# ── 官方 DeepSeek 端点（L2/L4 走这里：实测 11s/批 vs go 107s/批）──
DS_API_KEY = os.environ.get("DS_API_KEY", "")
DS_BASE_URL = os.environ.get("DS_BASE_URL", "https://api.deepseek.com/v1")
DS_ENDPOINT = {"base_url": DS_BASE_URL, "api_key": DS_API_KEY}

# ── 模型槽位池 ──
# 槽位与阶段解耦：换模型只改这里。槽位内按优先级排列（降级链）。
# 例外：verify 槽位是并行双验证语义，不走降级链。
# 按聚合后置 L5 方案（桌面 PDF）重排：
#   L2 只滤垃圾（deepseek flash 快）；L4 提取（deepseek flash 快，
#   kimi 只分流超长）；L5 双 Judge 保质量（禁 flash）。
SLOT_POOLS = {
    "relevance":   ["deepseek-v4-flash"],
    "quality":     ["qwen3.8-max"],
    "extract":     ["deepseek-v4-flash", "deepseek-v4-pro"],
    "verify":      ["qwen3.7-plus", "mimo-v2.5-pro"],
    "translate":   ["glm-5.3"],
    "duties_diff": ["glm-5.3"],
}

# ── 模型怪癖（探针实测）──
# kimi 系列只接受 temperature=1；qwen3.8-max 不支持 response_format
MODEL_TEMPERATURE_OVERRIDE = {"kimi-k3": 1.0, "kimi-k2.7-code": 1.0}
MODEL_NO_RESPONSE_FORMAT = {"qwen3.8-max", "qwen3.7-plus"}

# ── L5 聚合后置开关（桌面 PDF：紧急回退只需改这一行）──
POST_VERIFY_AFTER_AGGREGATE = True   # True=聚合后置校验；False=原始逐条 L5 基线
POST_VERIFY_ONLY_OUTPUT_ABNORMAL = True  # L5 只输出异常标签的技能，正常技能不返回
POST_VERIFY_BATCH_SIZE = 8           # L5 每批岗位数量上限（仅为数量上限，不能代替 token 切分）
POST_VERIFY_MAX_CONCURRENT = 3

# ── 并发：所有大模型阶段必须独立信号量池，严禁共用 ──
L2_MAX_CONCURRENT = 12
L4_FLASH_MAX_CONCURRENT = 8   # 官方 DeepSeek flash 队列并发（官方端点快，可放宽）
L4_KIMI_MAX_CONCURRENT = 4    # 官方 deepseek-v4-pro 队列并发
L5_MAX_CONCURRENT = 3

# ── L2/L4 串行化开关 ──
# True = L2 全部完成后 L4 才开始（官方 flash 单 key 限流下，
# 重叠会互相抢导致 missing 风暴；串行慢 ~20 分钟但稳）
# False = 流水线并行（L4 边出边提，快但 flash 过载时易 missing）
L2_L4_SERIAL = True
# 4000 = flash 批输入安全线（实测 flash 输入 24K 字符时输出 0）；
# >4000 或真脏（脏分≥2）→ pro 兜底
L4_SPLIT_TEXT_LEN_THRESHOLD = 4000   # 字符长度阈值
L4_SPLIT_DIRTY_SCORE_THRESHOLD = 2   # 脏分>=2 判定为脏样本

# ── 并发与限速（探针实测：5 并发全成功；6+ 出现连接超时）──
JD_MAX_CONCURRENT = int(os.environ.get("JD_MAX_CONCURRENT", "5"))
JD_TARGET_CONCURRENT = int(os.environ.get("JD_TARGET_CONCURRENT", "5"))
# 超时分层（实测）：连接 15s 快速失败；读 300s 给批量生成留足时间
# （kimi 单批提取实测 199s，180s 会掐死正常批）
JD_LLM_TIMEOUT = float(os.environ.get("JD_LLM_TIMEOUT", "45"))
JD_CONNECT_TIMEOUT = float(os.environ.get("JD_CONNECT_TIMEOUT", "15"))
JD_READ_TIMEOUT = float(os.environ.get("JD_READ_TIMEOUT", "300"))
JD_VERIFY_MODE = os.environ.get("JD_VERIFY_MODE", "full")  # full | suspicious_only

# ── 模型成本表（USD / 百万 token）：prompt, completion ──
MODEL_COST = {
    "glm-5.3-flash": (0.20, 0.40),
    "glm-5.3":       (0.80, 2.00),
    "kimi-k3":       (0.80, 2.00),
    "qwen3.8-max":   (0.80, 2.00),
}

# ── 旧常量兼容别名（Task 4 阶段迁移后删除）──
MODEL_STAGE1 = SLOT_POOLS["relevance"][0]
MODEL_STAGE2 = SLOT_POOLS["quality"][0]
MODEL_STAGE3 = SLOT_POOLS["extract"][0]
MODEL_DUTIES_DIFF = SLOT_POOLS["duties_diff"][0]

# ── 阈值（初始值，测试后调优） ──
RELEVANCE_CONFIDENCE = float(os.environ.get("JD_RELEVANCE_CONFIDENCE", "0.7"))
QUALITY_PASS = float(os.environ.get("JD_QUALITY_PASS", "0.65"))
QUALITY_REJECT = float(os.environ.get("JD_QUALITY_REJECT", "0.5"))
MAX_RETRY = int(os.environ.get("JD_MAX_RETRY", "3"))
BATCH_SIZE = int(os.environ.get("JD_BATCH_SIZE", "10"))
PREFILTER_THRESHOLD = float(os.environ.get("JD_PREFILTER_THRESHOLD", "0.5"))

# ── 乱码检测 ──
GARBLED_RATIO_THRESHOLD = float(os.environ.get("JD_GARBLED_RATIO", "0.25"))
GARBLED_MIN_LENGTH = 30

# ── 路径 ──
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "local"
EXCHANGE_DIR = REPO_ROOT / "exchange" / "m2"
SKILL_DICT_PATH = REPO_ROOT / "backend" / "app" / "skills" / "skill_dict_seed.json"
TESTS_DIR = REPO_ROOT / "backend" / "tests"

# 新数据包路径（m2-data-pack；可通过环境变量覆盖）
DATA_PACK_DIR = Path(os.environ.get("JD_DATA_PACK", str(DATA_DIR / "m2-data-pack")))
SIGNAL_SNAPSHOT_PATH = DATA_PACK_DIR / "信号数据" / "signal_snapshot.json"
# skill_dict 优先用本地 M2 快照中的 seed；不存在时使用正式词典。
if (DATA_PACK_DIR / "岗位数据" / "skill_dict_seed.json").exists():
    SKILL_DICT_PATH = DATA_PACK_DIR / "岗位数据" / "skill_dict_seed.json"
