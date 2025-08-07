import pytest
from typing import Dict, Any, Optional

class TestConfigProvider:
    
    def test_get_config_returns_value_when_key_exists(self):
        from infrastructure.config.settings import EnvironmentConfig
        config = EnvironmentConfig()
        config.set_config('TEST_KEY', 'test_value')
        
        result = config.get_config('TEST_KEY')
        
        assert result == 'test_value'
    
    def test_get_config_returns_none_when_key_not_exists(self):
        from infrastructure.config.settings import EnvironmentConfig
        config = EnvironmentConfig()
        
        result = config.get_config('NON_EXISTING_KEY')
        
        assert result is None
    
    def test_set_config_stores_value(self):
        from infrastructure.config.settings import EnvironmentConfig
        config = EnvironmentConfig()
        
        config.set_config('NEW_KEY', 'new_value')
        result = config.get_config('NEW_KEY')
        
        assert result == 'new_value'
    
    def test_get_all_config_returns_dict(self):
        from infrastructure.config.settings import EnvironmentConfig
        config = EnvironmentConfig()
        config.set_config('KEY1', 'value1')
        config.set_config('KEY2', 'value2')
        
        all_config = config.get_all_config()
        
        assert isinstance(all_config, dict)
        assert 'KEY1' in all_config
        assert 'KEY2' in all_config
        assert all_config['KEY1'] == 'value1'
        assert all_config['KEY2'] == 'value2'
    
    def test_validate_raises_error_when_required_config_missing(self):
        from infrastructure.config.settings import EnvironmentConfig
        config = EnvironmentConfig()
        config.set_config('DISCORD_BOT_TOKEN', '')
        config.set_config('OPENAI_API_KEY', '')
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert 'is required' in str(exc_info.value)
    
    def test_is_development_returns_true_when_environment_is_development(self):
        from infrastructure.config.settings import EnvironmentConfig
        config = EnvironmentConfig()
        config.set_config('ENVIRONMENT', 'development')
        
        result = config.is_development()
        
        assert result is True
    
    def test_is_production_returns_true_when_environment_is_production(self):
        from infrastructure.config.settings import EnvironmentConfig
        config = EnvironmentConfig()
        config.set_config('ENVIRONMENT', 'production')
        
        result = config.is_production()
        
        assert result is True