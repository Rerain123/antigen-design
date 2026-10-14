"""Perform a real MCP Streamable HTTP handshake against a running server."""

from __future__ import annotations

import argparse
import asyncio

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def check(url: str) -> None:
    async with streamable_http_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            scenarios = await session.call_tool("mock.list_scenarios", {})
            if scenarios.is_error:
                raise RuntimeError("mock.list_scenarios returned an MCP error")
            scenario_count = scenarios.structured_content["count"]
            if len(tools.tools) != 63:
                raise RuntimeError(f"expected 63 tools, received {len(tools.tools)}")
            if scenario_count != 25:
                raise RuntimeError(f"expected 25 scenarios, received {scenario_count}")
            print(f"protocol_version={initialized.protocol_version}")
            print(f"tool_count={len(tools.tools)}")
            print(f"scenario_count={scenario_count}")
            print("status=PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8101/mcp")
    args = parser.parse_args()
    asyncio.run(check(args.url))


if __name__ == "__main__":
    main()
