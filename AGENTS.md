# Agent Governance & Context

---
*Note: Global system memory is tracked securely outside this repository. Read architecture decisions from: `~/.agentdrive/brains/CentralBrain/projects/contextweave`*
1. **Broadcast**: Error Tracking: Whenever an error is encountered and fixed, document it in debugging.md. Format: ERROR: <Details> | Date: <date> | Status: <new/re-occur> | Fix: <Fix>
2. **Broadcast**: Startup Scripts: If start_all.sh and stop_all.sh scripts do not exist in the repository, you MUST create them to manage the project's services.
