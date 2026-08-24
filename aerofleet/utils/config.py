"""
Configuration management for Space Mission Architect.

Loads configuration from YAML files and environment variables,
with validation using Pydantic models.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from aerofleet.utils.exceptions import ConfigurationError


class LLMConfig(BaseSettings):
    """LLM configuration settings."""
    
    ollama_host: str = Field(default="http://localhost:11434", description="Ollama server URL")
    ollama_model: str = Field(default="llama3.2", description="Ollama model name")
    ollama_timeout: int = Field(default=300, description="Timeout in seconds")

    # "API" connection mode — see aerofleet.agents.openrouter_agent.
    # Prefer the runtime-mutable aerofleet.agents.runtime_settings singleton
    # for the actual value in use; these are just the env-var-seeded defaults.
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "meta-llama/llama-4-scout"

    model_config = SettingsConfigDict(env_prefix="")


class DatabaseConfig(BaseSettings):
    """Database configuration settings."""

    # validation_alias bypasses env_prefix below — this field is read from
    # plain DATABASE_URL (not DATABASE_DATABASE_URL), matching .env.example,
    # docker-compose.yml, and k8s/deployment.yaml, all of which set DATABASE_URL.
    database_url: str = Field(default="sqlite:///./aerofleet.db", validation_alias="DATABASE_URL")
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)
    echo: bool = Field(default=False)
    
    # populate_by_name: keep accepting the plain field name ("database_url")
    # from dicts/kwargs (YAML config, direct construction in tests) — an
    # explicit validation_alias otherwise restricts that field to *only*
    # the alias, which would break both of those call sites.
    model_config = SettingsConfigDict(env_prefix="DATABASE_", populate_by_name=True)


class RedisConfig(BaseSettings):
    """Redis cache configuration."""
    
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: Optional[str] = None
    
    # Cache TTL settings
    cache_ttl_trajectory: int = Field(default=3600)
    cache_ttl_llm_response: int = Field(default=7200)
    
    model_config = SettingsConfigDict(env_prefix="REDIS_")


class APIConfig(BaseSettings):
    """API server configuration."""
    
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    # Must stay 1: FleetState/DroneLinkRegistry/AsyncEventBus are module-level
    # singletons, not shared across worker processes — see the comment on
    # the Dockerfile's CMD for the full explanation.
    workers: int = Field(default=1)
    reload: bool = Field(default=True)
    
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8501",
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost",
        ]
    )
    cors_allow_credentials: bool = Field(default=True)
    
    rate_limit_per_minute: int = Field(default=60)
    
    model_config = SettingsConfigDict(env_prefix="API_")


class PathsConfig(BaseSettings):
    """File paths configuration."""

    project_root: Path
    city_graph_cache_path: Path
    components_db_path: Path
    saved_missions_path: Path

    model_config = SettingsConfigDict(env_prefix="")

    def __init__(self, **kwargs):
        if 'project_root' not in kwargs:
            # Auto-detect project root
            current_file = Path(__file__).resolve()
            # Navigate up from utils/config.py to project root
            project_root = current_file.parent.parent.parent
            kwargs['project_root'] = project_root

        # Set defaults based on project root
        pr = Path(kwargs['project_root'])
        kwargs.setdefault('city_graph_cache_path', pr / "data" / "city_cache")
        kwargs.setdefault('components_db_path', pr / "data" / "components.json")
        kwargs.setdefault('saved_missions_path', pr / "saved_missions")

        super().__init__(**kwargs)


class SimulationConfig(BaseSettings):
    """Fleet simulation configuration."""

    max_duration_hours: int = Field(default=24)
    time_step_seconds: int = Field(default=10)
    enable_anomaly_injection: bool = Field(default=True)
    anomaly_probability: float = Field(default=0.15)

    model_config = SettingsConfigDict(env_prefix="SIMULATION_")


class AgentConfig(BaseSettings):
    """Agent system configuration."""

    max_agents: int = Field(default=12)
    timeout: int = Field(default=60)
    enable_council_debate: bool = Field(default=True)
    use_mock_agents: bool = Field(default=False, description="Use MockLLMBackend instead of live Ollama")

    model_config = SettingsConfigDict(env_prefix="AGENT_")


class CityConfig(BaseSettings):
    """City / airspace configuration."""

    demo_city: str = Field(default="Pune, Maharashtra, India")
    regulatory_framework: str = Field(default="DGCA_2021")

    model_config = SettingsConfigDict(env_prefix="")


class FleetConfig(BaseSettings):
    """Fleet & battery default configuration."""

    battery_capacity_wh: float = Field(default=500.0)
    battery_reserve_margin: float = Field(default=0.20)
    drone_payload_kg: float = Field(default=5.0)
    depot_count: int = Field(default=6)

    model_config = SettingsConfigDict(env_prefix="DEFAULT_")


class Config(BaseSettings):
    """Main configuration class combining all settings."""
    
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    
    secret_key: str = Field(default="your-secret-key-here-change-in-production")
    
    # Feature flags
    enable_knowledge_base: bool = Field(default=True)
    enable_rl_optimizer: bool = Field(default=False)
    enable_report_generation: bool = Field(default=True)
    enable_3d_visualization: bool = Field(default=True)
    enable_metrics: bool = Field(default=True)
    
    # Sub-configurations
    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    city: CityConfig = Field(default_factory=CityConfig)
    fleet: FleetConfig = Field(default_factory=FleetConfig)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"   # Allow AGENT_MODEL_*, DASHBOARD_*, etc. without error
    )
    
    @classmethod
    def load_from_yaml(cls, config_path: Path) -> "Config":
        """Load configuration from YAML file."""
        if not config_path.exists():
            raise ConfigurationError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            yaml_config = yaml.safe_load(f)
        
        return cls(**yaml_config)
    
    def validate_paths(self) -> None:
        """Validate that required paths exist."""
        if not self.paths.project_root.exists():
            raise ConfigurationError(f"Project root not found: {self.paths.project_root}")
        
        # Create directories if they don't exist
        self.paths.saved_missions_path.mkdir(parents=True, exist_ok=True)


# Global configuration instance
_config: Optional[Config] = None


def get_config(reload: bool = False) -> Config:
    """
    Get the global configuration instance.
    
    Priority (highest to lowest):
      1. Environment variables (including those in .env file)
      2. YAML config file values
      3. Pydantic field defaults

    Args:
        reload: Force reload of configuration

    Returns:
        Config instance
    """
    global _config

    if _config is None or reload:
        # Load .env file into os.environ FIRST so env vars take priority
        from pathlib import Path as _Path
        env_file = _Path(".env")
        if env_file.exists():
            try:
                from dotenv import load_dotenv
                # override=False: shell-set env vars must win over .env file
                # defaults (that's the whole point of being able to export
                # e.g. USE_MOCK_AGENTS=true or OLLAMA_HOST before starting
                # the app) — only fill in keys the shell hasn't already set.
                load_dotenv(env_file, override=False)
            except ImportError:
                pass  # python-dotenv not installed; rely on shell env vars

        # Try to load from YAML (provides non-sensitive defaults)
        config_dir = Path(os.getenv("CONFIG_DIR", "config"))
        env = os.getenv("ENVIRONMENT", "development")

        yaml_path = config_dir / f"{env}.yaml"
        if not yaml_path.exists():
            yaml_path = config_dir / "default.yaml"

        if yaml_path.exists():
            _config = Config.load_from_yaml(yaml_path)
        else:
            # Fall back to environment variables only
            _config = Config()

        # Env vars have already been loaded; now patch any sub-config values
        # that Pydantic may have missed because YAML took priority.
        # Explicitly re-read OLLAMA_HOST from env so the remote host wins.
        ollama_host_env = os.environ.get("OLLAMA_HOST")
        if ollama_host_env:
            _config.llm.ollama_host = ollama_host_env

        _config.validate_paths()

    return _config


def update_config(**kwargs) -> None:
    """Update configuration values at runtime."""
    global _config
    if _config is None:
        _config = get_config()
    
    for key, value in kwargs.items():
        if hasattr(_config, key):
            setattr(_config, key, value)
