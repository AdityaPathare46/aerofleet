"""Custom exceptions for Space Mission Architect."""


class SpaceMissionArchitectError(Exception):
    """Base exception for all Space Mission Architect errors."""
    pass


class ConfigurationError(SpaceMissionArchitectError):
    """Raised when configuration is invalid or missing."""
    pass


class TrajectoryCalculationError(SpaceMissionArchitectError):
    """Raised when trajectory calculation fails."""
    
    def __init__(self, message: str, origin: str = None, target: str = None):
        super().__init__(message)
        self.origin = origin
        self.target = target


class AgentCommunicationError(SpaceMissionArchitectError):
    """Raised when agent communication fails or LLM is unavailable."""
    
    def __init__(self, message: str, agent_id: str = None):
        super().__init__(message)
        self.agent_id = agent_id


class DataValidationError(SpaceMissionArchitectError):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, field: str = None, value: any = None):
        super().__init__(message)
        self.field = field
        self.value = value


class ResourceNotFoundError(SpaceMissionArchitectError):
    """Raised when a required resource is not found."""
    
    def __init__(self, message: str, resource_type: str = None, resource_id: str = None):
        super().__init__(message)
        self.resource_type = resource_type
        self.resource_id = resource_id


class SPICEKernelError(SpaceMissionArchitectError):
    """Raised when SPICE kernel operations fail."""
    pass


class SimulationError(SpaceMissionArchitectError):
    """Raised when mission simulation encounters an error."""
    pass


class StorageError(SpaceMissionArchitectError):
    """Raised when data storage/retrieval fails."""
    
    def __init__(self, message: str, operation: str = None):
        super().__init__(message)
        self.operation = operation


class PhysicsCalculationError(SpaceMissionArchitectError):
    """Raised when physics calculations fail."""
    pass


class ComponentNotFoundError(ResourceNotFoundError):
    """Raised when a spacecraft component is not found in the database."""
    pass


class MissionValidationError(DataValidationError):
    """Raised when mission specification validation fails."""
    pass
