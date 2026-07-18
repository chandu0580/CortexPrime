from __future__ import annotations

import argparse
import os
import sys
from string import Template


_AGENT_TEMPLATE = Template('''from __future__ import annotations

from typing import Any, Dict

from backend.agent_sdk import CortexAgent, MissionContext, MissionResult, tool
from backend.agent_sdk.types import AgentConfig, AgentStatus


class ${class_name}(CortexAgent):
    def __init__(self):
        config = AgentConfig(
            agent_type="${agent_type}",
            agent_name="${agent_name}",
            version="1.0.0",
            description="${description}",
            tags=[${tags}],
        )
        super().__init__(config)

    async def execute(self, context: MissionContext) -> MissionResult:
        return MissionResult(
            mission_id=context.mission_id,
            status=AgentStatus.COMPLETED,
            output={"message": "Hello from ${agent_name}!"},
        )
''')


_SETUP_TEMPLATE = Template('''from setuptools import setup, find_packages

setup(
    name="${package_name}",
    version="1.0.0",
    packages=find_packages(),
    install_requires=["cortexprime>=1.0.0"],
    python_requires=">=3.11",
    entry_points={
        "cortexprime.agents": [
            "${agent_type}=${package_name}.agent:${class_name}",
        ],
    },
)
''')


def scaffold(args: argparse.Namespace):
    agent_type = args.name.replace(" ", "_").replace("-", "_").lower()
    class_name = "".join(word.capitalize() for word in agent_type.split("_"))
    agent_name = args.name.replace("_", " ").title()
    description = args.description or f"A custom {agent_name} agent"
    tags = ", ".join(f'"{t}"' for t in (args.tags or []))

    os.makedirs(args.output, exist_ok=True)
    pkg_dir = os.path.join(args.output, agent_type)
    os.makedirs(pkg_dir, exist_ok=True)

    agent_path = os.path.join(pkg_dir, "agent.py")
    with open(agent_path, "w") as f:
        f.write(_AGENT_TEMPLATE.substitute(
            class_name=class_name,
            agent_type=agent_type,
            agent_name=agent_name,
            description=description,
            tags=tags,
        ))

    init_path = os.path.join(pkg_dir, "__init__.py")
    with open(init_path, "w") as f:
        f.write(f"from {agent_type}.agent import {class_name}\n")

    setup_path = os.path.join(args.output, "setup.py")
    with open(setup_path, "w") as f:
        f.write(_SETUP_TEMPLATE.substitute(
            package_name=agent_type,
            agent_type=agent_type,
            class_name=class_name,
        ))

    print(f"Scaffolded agent '{agent_name}' at {pkg_dir}")
    print(f"  agent.py  - Agent implementation")
    print(f"  __init__.py - Package exports")
    print(f"  setup.py  - Installable package")
    print(f"\nTo install: pip install -e {args.output}")


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new CortexPrime agent")
    parser.add_argument("name", help="Agent name (e.g. 'code_reviewer')")
    parser.add_argument("--output", "-o", default=".", help="Output directory")
    parser.add_argument("--description", "-d", help="Agent description")
    parser.add_argument("--tags", "-t", nargs="*", default=[], help="Agent tags")
    args = parser.parse_args()
    scaffold(args)


if __name__ == "__main__":
    main()
