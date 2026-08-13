"""JD Filter 全局配置 —— 换供应商只需修改此文件。"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 读取 backend/.env（gitignore 保护，含 LLM_API_KEY/LLM_BASE_URL 等，安装即用）
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / "backend" / ".env")

# ── API ──
# 支持 OpenAI-compatible API（DeepSeek / 其他供应商）
# 设置环境变量后运行，也可直接修改下方默认值
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")

# 四个独立模型槽位 —— 三阶段 + duties diff 各用各的
MODEL_STAGE1 = os.environ.get("JD_MODEL_STAGE1", "deepseek-v4-flash")
MODEL_STAGE2 = os.environ.get("JD_MODEL_STAGE2", "deepseek-v4-pro")
MODEL_STAGE3 = os.environ.get("JD_MODEL_STAGE3", "deepseek-v4-pro")
MODEL_DUTIES_DIFF = os.environ.get("JD_MODEL_DUTIES_DIFF", "deepseek-v4-flash")

# ── 阈值（初始值，测试后调优） ──
RELEVANCE_CONFIDENCE = float(os.environ.get("JD_RELEVANCE_CONFIDENCE", "0.7"))
QUALITY_PASS = float(os.environ.get("JD_QUALITY_PASS", "0.65"))
QUALITY_REJECT = float(os.environ.get("JD_QUALITY_REJECT", "0.5"))
MAX_RETRY = int(os.environ.get("JD_MAX_RETRY", "3"))
BATCH_SIZE = int(os.environ.get("JD_BATCH_SIZE", "10"))

# ── 乱码检测 ──
GARBLED_RATIO_THRESHOLD = float(os.environ.get("JD_GARBLED_RATIO", "0.25"))
GARBLED_MIN_LENGTH = 30

# ── 路径 ──
_REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(__file__).parent / "data"          # checkpoint 中间产物（不入库）
EXCHANGE_DIR = _REPO_ROOT / "exchange" / "m2"      # 交接产出（D26 小写）
SKILL_DICT_PATH = _REPO_ROOT / "backend" / "app" / "skills" / "skill_dict_seed.json"
if not SKILL_DICT_PATH.exists():
    SKILL_DICT_PATH = Path(__file__).parent / "skill_dict_seed.json"
TESTS_DIR = Path(__file__).parent / "tests"
