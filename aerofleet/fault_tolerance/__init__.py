"""
Proactive Fault Tolerance and Recovery Framework.

New in v2.0:
  - Predictive Diagnostics & Prognostics — RF + SOM hybrid (Section 2)
  - LIME-based XAI fault analysis (Section 2)
  - PPO fault recovery controller (Section 2)
  - Multi-fault simultaneous handler (Section 2)
  - Distributed recovery agent architecture (Section 2)
  - Edge AI optimizer for onboard inference (Section 2)
  - Sim2Real transfer layer (Section 2)
  - Online model adaptation (Section 2)
"""

from .predictive_diagnostics import PredictiveDiagnostics, AnomalyReport
from .xai_fault_analysis import XAIFaultAnalyzer
from .ppo_fault_recovery import PPOFaultRecoveryController
from .multi_fault_handler import MultiFaultHandler, FaultType
from .distributed_recovery import DistributedRecoveryOrchestrator
from .edge_ai_optimizer import EdgeAIOptimizer
from .sim2real import Sim2RealTransfer
from .online_adaptation import OnlineAdaptationEngine

__all__ = [
    "PredictiveDiagnostics",
    "AnomalyReport",
    "XAIFaultAnalyzer",
    "PPOFaultRecoveryController",
    "MultiFaultHandler",
    "FaultType",
    "DistributedRecoveryOrchestrator",
    "EdgeAIOptimizer",
    "Sim2RealTransfer",
    "OnlineAdaptationEngine",
]
