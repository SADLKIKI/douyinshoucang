"""
配置管理模块
加载和验证 config.yaml 配置文件
"""
import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


CONFIG_FILE = "config.yaml"


@dataclass
class DouyinConfig:
    chrome_debug_port: int = 9222
    user_data_dir: str = "%LOCALAPPDATA%/DyD_Chrome"
    max_downloads_per_task: int = 100


@dataclass
class WhisperConfig:
    model_size: str = "medium"
    device: str = "cuda"
    compute_type: str = "int8"
    language: str = "zh"


@dataclass
class LLMConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = "gpt-4o"
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class FeishuTableIds:
    videos: str = ""
    transcripts: str = ""
    analysis: str = ""
    topics: str = ""
    competitors: str = ""
    hotspots: str = ""
    logs: str = ""


@dataclass
class FeishuConfig:
    app_id: str = ""
    app_secret: str = ""
    bitable_app_token: str = ""
    table_ids: FeishuTableIds = field(default_factory=FeishuTableIds)


@dataclass
class SchedulerConfig:
    enabled: bool = True
    interval_hours: int = 4
    timezone: str = "Asia/Shanghai"


@dataclass
class AppConfig:
    douyin: DouyinConfig = field(default_factory=DouyinConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    feishu: FeishuConfig = field(default_factory=FeishuConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    dyd_path: str = "D:\\AI\\DyD下载器"
    data_dir: str = "data"
    _config_path: Optional[str] = None

    @property
    def base_dir(self) -> Path:
        """项目根目录"""
        return Path(__file__).parent.parent

    @property
    def data_path(self) -> Path:
        """数据目录绝对路径"""
        return self.base_dir / self.data_dir

    @property
    def downloads_path(self) -> Path:
        return self.data_path / "downloads"

    @property
    def transcripts_path(self) -> Path:
        return self.data_path / "transcripts"

    @property
    def reports_path(self) -> Path:
        return self.data_path / "reports"

    @property
    def db_path(self) -> Path:
        return self.data_path / "douylike.db"


def _dict_to_config(data: dict) -> AppConfig:
    """将 YAML 字典转换为 AppConfig 对象"""
    cfg = AppConfig()

    # douyin
    d = data.get("douyin", {})
    cfg.douyin = DouyinConfig(**{k: v for k, v in d.items() if k in DouyinConfig.__dataclass_fields__})

    # whisper
    w = data.get("whisper", {})
    cfg.whisper = WhisperConfig(**{k: v for k, v in w.items() if k in WhisperConfig.__dataclass_fields__})

    # llm
    l = data.get("llm", {})
    cfg.llm = LLMConfig(**{k: v for k, v in l.items() if k in LLMConfig.__dataclass_fields__})

    # feishu
    f = data.get("feishu", {})
    table_ids_data = f.pop("table_ids", {})
    cfg.feishu = FeishuConfig(**{k: v for k, v in f.items() if k in FeishuConfig.__dataclass_fields__})
    cfg.feishu.table_ids = FeishuTableIds(**{k: v for k, v in table_ids_data.items() if k in FeishuTableIds.__dataclass_fields__})

    # scheduler
    s = data.get("scheduler", {})
    # 支持旧版 cron_hour/cron_minute 和新版 interval_hours
    if "interval_hours" not in s and "cron_hour" in s:
        s["interval_hours"] = 4  # 默认4小时
    cfg.scheduler = SchedulerConfig(**{k: v for k, v in s.items() if k in SchedulerConfig.__dataclass_fields__})

    # simple fields
    cfg.dyd_path = data.get("dyd_path", cfg.dyd_path)
    cfg.data_dir = data.get("data_dir", cfg.data_dir)

    return cfg


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """加载配置文件"""
    if config_path is None:
        config_path = str(Path(__file__).parent.parent / CONFIG_FILE)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    cfg = _dict_to_config(data)
    cfg._config_path = config_path

    # 确保数据目录存在
    cfg.data_path.mkdir(parents=True, exist_ok=True)
    cfg.downloads_path.mkdir(parents=True, exist_ok=True)
    cfg.transcripts_path.mkdir(parents=True, exist_ok=True)
    cfg.reports_path.mkdir(parents=True, exist_ok=True)

    return cfg


def save_config(cfg: AppConfig):
    """保存配置到文件"""
    config_path = cfg._config_path or str(Path(__file__).parent.parent / CONFIG_FILE)

    data = {
        "douyin": {
            "chrome_debug_port": cfg.douyin.chrome_debug_port,
            "user_data_dir": cfg.douyin.user_data_dir,
            "max_downloads_per_task": cfg.douyin.max_downloads_per_task,
        },
        "whisper": {
            "model_size": cfg.whisper.model_size,
            "device": cfg.whisper.device,
            "compute_type": cfg.whisper.compute_type,
            "language": cfg.whisper.language,
        },
        "llm": {
            "base_url": cfg.llm.base_url,
            "api_key": cfg.llm.api_key,
            "model": cfg.llm.model,
            "max_tokens": cfg.llm.max_tokens,
            "temperature": cfg.llm.temperature,
        },
        "feishu": {
            "app_id": cfg.feishu.app_id,
            "app_secret": cfg.feishu.app_secret,
            "bitable_app_token": cfg.feishu.bitable_app_token,
            "table_ids": {
                "videos": cfg.feishu.table_ids.videos,
                "transcripts": cfg.feishu.table_ids.transcripts,
                "analysis": cfg.feishu.table_ids.analysis,
                "topics": cfg.feishu.table_ids.topics,
                "competitors": cfg.feishu.table_ids.competitors,
                "hotspots": cfg.feishu.table_ids.hotspots,
                "logs": cfg.feishu.table_ids.logs,
            },
        },
        "scheduler": {
            "enabled": cfg.scheduler.enabled,
            "interval_hours": cfg.scheduler.interval_hours,
            "timezone": cfg.scheduler.timezone,
        },
        "dyd_path": cfg.dyd_path,
        "data_dir": cfg.data_dir,
    }

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
