import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp.toolkit import MCPToolkit
import os

async def main():
    import sys
    mcp_script = os.path.abspath("mcp_stdio.py")
    server_params = StdioServerParameters(command=sys.executable, args=[mcp_script])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            toolkit = MCPToolkit(session=session)
            await toolkit.initialize()
            tools = toolkit.get_tools()
            print([t.name for t in tools])

if __name__ == "__main__":
    asyncio.run(main())
