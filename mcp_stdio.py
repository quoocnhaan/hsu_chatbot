import asyncio
from app.mcp_server import mcp

async def main():
    if hasattr(mcp, "run_stdio_async"):
        await mcp.run_stdio_async()
    else:
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read_stream, write_stream):
            await mcp.run(
                read_stream,
                write_stream,
                mcp.create_initialization_options()
            )

if __name__ == "__main__":
    asyncio.run(main())
