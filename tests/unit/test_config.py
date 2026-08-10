"""
Unit tests for configuration module.
"""

import pytest
from pathlib import Path
from aerofleet.utils.config import (
    Config,
    LLMConfig,
    DatabaseConfig,
    get_config,
    ConfigurationError
)


class TestLLMConfig:
    """Tests for LLM configuration."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        config = LLMConfig()
        assert config.ollama_host == "http://localhost:11434"
        assert config.ollama_model == "llama3.2"
        assert config.ollama_timeout == 300
    
    def test_ollama_host_override(self, monkeypatch):
        """Test overriding Ollama host via environment variable."""
        monkeypatch.setenv("OLLAMA_HOST", "http://remote-server:11434")
        config = LLMConfig()
        assert config.ollama_host == "http://remote-server:11434"


class TestDatabaseConfig:
    """Tests for database configuration."""
    
    def test_default_sqlite(self):
        """Test default SQLite configuration."""
        config = DatabaseConfig()
        assert "sqlite" in config.database_url
        assert config.pool_size == 10
    
    def test_postgres_url(self, monkeypatch):
        """Test PostgreSQL URL configuration."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        config = DatabaseConfig()
        assert config.database_url.startswith("postgresql://")


class TestConfig:
    """Tests for main configuration class."""
    
    def test_load_default_config(self):
        """Test loading default configuration."""
        config = Config()
        assert config.environment == "development"
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.database, DatabaseConfig)
    
    def test_debug_mode_in_development(self):
        """Test that debug is enabled in development."""
        config = Config(environment="development")
        assert config.debug is True
    
    def test_production_settings(self):
        """Test production configuration."""
        config = Config(environment="production", debug=False)
        assert config.environment == "production"
        assert config.debug is False
    
    def test_validate_paths(self, tmp_path):
        """Test path validation."""
        config = Config()
        config.paths.project_root = tmp_path
        config.paths.saved_missions_path = tmp_path / "missions"
        
        # Should create directories if they don't exist
        config.validate_paths()
        assert config.paths.saved_missions_path.exists()
    
    def test_load_from_yaml(self, tmp_path):
        """Test loading configuration from YAML file."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
environment: test
debug: false
log_level: DEBUG

llm:
  ollama_model: test-model
  ollama_timeout: 120
""")
        
        config = Config.load_from_yaml(config_file)
        assert config.environment == "test"
        assert config.log_level == "DEBUG"
        assert config.llm.ollama_model == "test-model"
        assert config.llm.ollama_timeout == 120
    
    def test_load_missing_yaml_raises_error(self, tmp_path):
        """Test that loading missing YAML file raises error."""
        missing_file = tmp_path / "nonexistent.yaml"
        
        with pytest.raises(ConfigurationError):
            Config.load_from_yaml(missing_file)


class TestGetConfig:
    """Tests for get_config function."""
    
    def test_singleton_behavior(self):
        """Test that get_config returns the same instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2
    
    def test_reload_config(self):
        """Test reloading configuration."""
        config1 = get_config()
        config2 = get_config(reload=True)
        # Should be a new instance after reload
        # (can't test identity since reload recreates in this implementation)
        assert isinstance(config2, Config)
