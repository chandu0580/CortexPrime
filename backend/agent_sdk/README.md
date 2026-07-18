# CortexPrime Agent SDK

Build custom agents for the CortexPrime AI Agent Operating System.

## Installation

```bash
pip install cortexprime-agent-sdk
```

## Quick Start

```python
from cortexprime import CortexAgent, MissionContext, MissionResult, tool
from cortexprime.types import AgentConfig, AgentStatus


class MyAgent(CortexAgent):
    def __init__(self):
        config = AgentConfig(
            agent_type="my_agent",
            agent_name="My Agent",
            version="1.0.0",
            description="A custom agent",
        )
        super().__init__(config)

    @tool
    async def my_tool(self, param: str, context: MissionContext) -> dict:
        return {"result": f"Processed: {param}"}

    async def execute(self, context: MissionContext) -> MissionResult:
        return MissionResult(
            mission_id=context.mission_id,
            status=AgentStatus.COMPLETED,
            output={"message": "Hello from My Agent!"},
        )
```

## CLI Scaffolding

```bash
cortexprime-scaffold my_agent --output ./my-agent-package
```
