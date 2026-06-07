"""
Diagnostic: prove the persistent ClaudeSDKClient pattern is cheaper than query().

Run from inside WSL:
    source venv/bin/activate
    python test_sdk.py

Expected: call #1 reports cache_creation_input_tokens (~11k), call #2 reports
cache_read_input_tokens (~11k) and near-zero cache_creation — confirming the
second call leverages the cached system context.
"""

import asyncio
import shutil
import sys

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import AssistantMessage, TextBlock, ResultMessage


async def run_one(client, label, prompt):
    print(f"\n=== {label} ===")
    await client.query(prompt)
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"  reply: {block.text.strip()!r}")
        elif isinstance(message, ResultMessage):
            usage = message.usage or {}
            print(f"  cost:               ${message.total_cost_usd:.5f}")
            print(f"  input_tokens:       {usage.get('input_tokens', 0)}")
            print(f"  cache_creation:     {usage.get('cache_creation_input_tokens', 0)}")
            print(f"  cache_read:         {usage.get('cache_read_input_tokens', 0)}")
            print(f"  output_tokens:      {usage.get('output_tokens', 0)}")


async def main():
    print(f"Python:        {sys.version.split()[0]}")
    print(f"claude binary: {shutil.which('claude') or '!! NOT FOUND on PATH'}")

    options = ClaudeAgentOptions(
        allowed_tools=[],
        system_prompt="You are a terse assistant. Reply with exactly what is requested, nothing else.",
    )

    async with ClaudeSDKClient(options=options) as client:
        await run_one(client, "Call 1 (cold — cache creation)", "Reply with exactly: ALPHA")
        await run_one(client, "Call 2 (warm — cache should be read)", "Reply with exactly: BETA")


if __name__ == "__main__":
    asyncio.run(main())
