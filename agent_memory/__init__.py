"""
agent_memory — Persistent episodic memory for Space Mission Architect agents.

Uses ChromaDB as a local vector store so each agent remembers:
  - Past scenario failures and the corrections that fixed them
  - Successful mission plans that passed all evaluator checks

Memory is loaded at agent startup and injected as context before debate begins.
"""
