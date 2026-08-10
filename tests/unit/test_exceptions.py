"""
Unit tests for custom exceptions.
"""

import pytest
from aerofleet.utils.exceptions import (
    SpaceMissionArchitectError,
    ConfigurationError,
    TrajectoryCalculationError,
    AgentCommunicationError,
    DataValidationError,
    ResourceNotFoundError,
    SPICEKernelError,
    StorageError
)


class TestBaseException:
    """Tests for base exception class."""
    
    def test_base_exception_can_be_raised(self):
        """Test that base exception can be instantiated and raised."""
        with pytest.raises(SpaceMissionArchitectError):
            raise SpaceMissionArchitectError("Test error")
    
    def test_base_exception_message(self):
        """Test that exception message is preserved."""
        error_msg = "Something went wrong"
        exc = SpaceMissionArchitectError(error_msg)
        assert str(exc) == error_msg


class TestConfigurationError:
    """Tests for ConfigurationError."""
    
    def test_configuration_error_inherits_from_base(self):
        """Test that ConfigurationError inherits from base."""
        assert issubclass(ConfigurationError, SpaceMissionArchitectError)
    
    def test_configuration_error_can_be_caught(self):
        """Test that ConfigurationError can be caught."""
        with pytest.raises(ConfigurationError) as exc_info:
            raise ConfigurationError("Invalid config")
        
        assert "Invalid config" in str(exc_info.value)


class TestTrajectoryCalculationError:
    """Tests for TrajectoryCalculationError."""
    
    def test_trajectory_error_with_metadata(self):
        """Test trajectory error with origin and target."""
        exc = TrajectoryCalculationError(
            "Calculation failed",
            origin="EARTH",
            target="MARS"
        )
        assert exc.origin == "EARTH"
        assert exc.target == "MARS"
        assert "Calculation failed" in str(exc)
    
    def test_trajectory_error_without_metadata(self):
        """Test trajectory error without metadata."""
        exc = TrajectoryCalculationError("Calculation failed")
        assert exc.origin is None
        assert exc.target is None


class TestAgentCommunicationError:
    """Tests for AgentCommunicationError."""
    
    def test_agent_error_with_agent_id(self):
        """Test agent error with agent ID."""
        exc = AgentCommunicationError("Agent timeout", agent_id="ORBITAL")
        assert exc.agent_id == "ORBITAL"
    
    def test_agent_error_without_agent_id(self):
        """Test agent error without agent ID."""
        exc = AgentCommunicationError("LLM unavailable")
        assert exc.agent_id is None


class TestDataValidationError:
    """Tests for DataValidationError."""
    
    def test_validation_error_with_field(self):
        """Test validation error with field information."""
        exc = DataValidationError(
            "Invalid value",
            field="mass",
            value=-100
        )
        assert exc.field == "mass"
        assert exc.value == -100
    
    def test_validation_error_minimal(self):
        """Test validation error with minimal info."""
        exc = DataValidationError("Validation failed")
        assert exc.field is None
        assert exc.value is None


class TestResourceNotFoundError:
    """Tests for ResourceNotFoundError."""
    
    def test_resource_error_with_type_and_id(self):
        """Test resource error with type and ID."""
        exc = ResourceNotFoundError(
            "Mission not found",
            resource_type="mission",
            resource_id="12345"
        )
        assert exc.resource_type == "mission"
        assert exc.resource_id == "12345"


class TestStorageError:
    """Tests for StorageError."""
    
    def test_storage_error_with_operation(self):
        """Test storage error with operation."""
        exc = StorageError("Database write failed", operation="save")
        assert exc.operation == "save"
    
    def test_storage_error_without_operation(self):
        """Test storage error without operation."""
        exc = StorageError("Connection lost")
        assert exc.operation is None


class TestExceptionHierarchy:
    """Tests for exception hierarchy."""
    
    def test_all_inherit_from_base(self):
        """Test that all custom exceptions inherit from base."""
        exceptions = [
            ConfigurationError,
            TrajectoryCalculationError,
            AgentCommunicationError,
            DataValidationError,
            ResourceNotFoundError,
            SPICEKernelError,
            StorageError
        ]
        
        for exc_class in exceptions:
            assert issubclass(exc_class, SpaceMissionArchitectError)
    
    def test_can_catch_with_base_exception(self):
        """Test that all exceptions can be caught with base class."""
        with pytest.raises(SpaceMissionArchitectError):
            raise ConfigurationError("test")
        
        with pytest.raises(SpaceMissionArchitectError):
            raise TrajectoryCalculationError("test")
        
        with pytest.raises(SpaceMissionArchitectError):
            raise AgentCommunicationError("test")
