"""Exercise the real Sites MCP server over stdio with isolated state."""
import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[3]

class SitesMcpStartupTest(unittest.TestCase):
    def test_discovery_and_ledger(self):
        async def exercise(directory):
            env = dict(os.environ, SITES_MCP_TRANSPORT="stdio",
                       KEX_SITES_DB=f"{directory}/sites.sqlite3",
                       KEX_SITES_STORE=f"{directory}/objects",
                       KEX_SITES_PUBLISH_ROOT=f"{directory}/published")
            params = StdioServerParameters(command=sys.executable,
                args=[str(ROOT / "plugins/sites/server/mcp_server.py")], env=env)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = {tool.name for tool in tools.tools}
                    self.assertTrue({"sites_list", "site_create", "deploy", "estate_import", "ledger_verify"} <= names)
                    result = await session.call_tool("ledger_verify", {})
                    self.assertFalse(result.isError)
                    self.assertIn('"ok": true', result.content[0].text)
        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(exercise(directory))

if __name__ == "__main__":
    unittest.main()
