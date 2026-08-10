from abc import ABC, abstractmethod
from typing import Dict, Any

class AgentInterface(ABC):
    """
    The abstract definition of the Space Mission Architect Agent.
    This enforces a standard structure for any AI model we plug in (GPT-4, Llama-3, Gemini).
    """

    @abstractmethod
    def interpret_mission(self, user_prompt: str) -> Dict[str, Any]:
        """
        Takes a natural language prompt (e.g. "Plan a mission to Mars") 
        and returns a structured dictionary of objectives.
        """
        pass

    @abstractmethod
    def reason(self, context_data: Dict[str, Any]) -> str:
        """
        Performs Chain-of-Thought reasoning based on the provided data.
        """
        pass

    @abstractmethod
    def plan_trajectory(self, origin: str, target: str, constraints: Dict[str, Any]):
        """
        Generates a high-level flight plan using the Data Loader tools.
        """
        pass