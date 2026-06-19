# LangGraph & Model Context Protocol (MCP) Architecture Guide

This guide explains how to build a modern Agentic AI system by connecting a LangGraph ReAct agent to external tools using the Model Context Protocol (MCP).

---

## Phase 1: Build the MCP Server (The Tool Provider)
The MCP Server acts as an independent, secure backend that exposes your database or APIs to any AI agent.

1. **Define the Tools:**
   Create standard definitions for your tools (e.g., `inputSchema`, `name`, `description`). This tells the AI *how* to use the tool.
2. **Implement `@mcp.call_tool()`:**
   Write a single central handler function (`handle_call_tool`) decorated with `@mcp.call_tool()`. This function catches the JSON-RPC requests, extracts arguments (like JWT tokens), queries your database, and returns data formatted as an array of MCP `Content` objects (e.g., `TextContent`).
3. **Create the Stdio Entrypoint:**
   Create a small script (e.g., `mcp_stdio.py`) that acts as the transport layer. This script boots up the server and listens to the terminal's standard input/output (`stdio`) pipes so the client can talk to it.

---

## Phase 2: Build the LangGraph Agent (The Brain)
LangGraph is the loop that manages the AI's "thinking" process and triggers the tools when needed.

1. **Initialize the MCP Client:**
   Connect to the MCP server using `stdio_client` and create a `ClientSession` through a background pipe.
2. **Extract LangChain Tools:**
   Use `MCPToolkit(session)` to automatically translate the raw MCP tools into standard LangChain tool objects.
3. **Combine Your Two Types of Tools:**
   Your graph actually runs two completely different types of tools side-by-side:
   - **Local Tools (`@tool`)**: Standard LangChain tools built directly in your Python code (e.g., `@tool def search_university_handbook()`). When the `ToolNode` runs this, it executes it exactly like a normal Python function (`result = search(...)`).
   - **Remote MCP Tools**: Tools extracted from your MCP Server (e.g., `get_my_grades`). To the LLM, they look identical to local tools. However, when the `ToolNode` runs this, the LangChain wrapper serializes the request into **JSON-RPC** and pipes it down the `stdio` terminal to your remote `mcp_server.py` to be executed.
4. **Bind Tools to the LLM:**
   Initialize your LLM (e.g., `ChatOllama`) and run `llm.bind_tools(all_tools)`. This step is crucial—it teaches the LLM that these tools exist and how to format a request for them.
5. **Define Graph Nodes:**
   - **`agent` node**: Runs the LLM and generates responses or tool calls.
   - **`tools` node**: Uses `ToolNode(tools=all_tools)` to execute the requested tools.
   - **`custom` nodes**: Any extra logic (like formatting or guardrails) you want to run before ending.
6. **Define Graph Edges (The Router):**
   - **Conditional Edge**: Attach a router function (e.g., `should_continue`) to the `agent` node. If the LLM generates `message.tool_calls`, route traffic to the `tools` node. Otherwise, route to the final custom node.
   - **Static Edge**: Define a hardcoded rule (`add_edge("tools", "agent")`) that forces the graph to loop back to the agent the moment a tool finishes executing.
7. **Compile the Graph:**
   Combine the nodes and edges using `StateGraph(MessagesState)` and compile it into an executable workflow.

### How the LLM Knows the Tool Schema (Function Calling)
A common question is: *How does the LLM know exactly what JSON arguments to generate (like the JWT token) when it decides to call an MCP tool?*

This is handled seamlessly through **JSON Schema** translation:
1. **Server Definition:** In `mcp_server.py`, every tool is registered using `@mcp.list_tools()`. This function returns the name, description, and strict `inputSchema` (in JSON Schema format) for each tool.
2. **Client Fetch:** When `chatbot.py` starts, the `MCPToolkit` requests this list of tools and their exact JSON schemas from the server.
3. **LLM Binding:** When we run `llm.bind_tools(all_tools)`, LangChain takes the raw JSON Schemas and translates them into the native "Function Calling API" payload expected by the specific LLM (e.g., Qwen/Ollama).
4. **Execution:** The LLM reads this hidden payload alongside the conversation. Because it is highly trained on function calling, when it realizes it needs to fetch grades, it looks at the provided schema for `get_my_grades`, sees it requires a `token` string, reads the token from the system prompt, and natively outputs the perfectly-formatted JSON structure (`{"token": "..."}`).

---

## The Execution Workflow (End-to-End)

Here is exactly what happens when a user sends a message:

1. **Input:** The user sends a message (e.g., *"What are my grades?"*). FastAPI injects the message and the user's secret JWT token into the LangGraph `MessagesState`.
2. **Agent Thinking:** The Graph enters the `agent` node. The LLM reads the system prompt (containing the token) and the user's message.
3. **Tool Call Generation:** Realizing it needs external data, the LLM stops generating conversational text and instead outputs a structured JSON block inside `message.tool_calls` requesting the `get_my_grades` tool.
4. **The Router:** The `should_continue` conditional edge sees the `tool_calls` array and forcibly routes the graph into the `ToolNode`.
5. **MCP Execution:** The `ToolNode` calls the LangChain MCP wrapper. The wrapper serializes the request into JSON-RPC and fires it down the pipe. The `@mcp.call_tool` function in the MCP server catches it, fetches the grades from MySQL, and returns the data through the pipe.
6. **State Update:** The LangChain wrapper receives the raw data, packages it neatly into a `ToolMessage`, and LangGraph appends this message to the conversation history in `MessagesState`.
7. **The Loop:** Following the static edge, the Graph loops immediately back to the `agent` node. 
8. **Final Answer:** The LLM reads the entire history again—this time including the `ToolMessage` with the actual grades! It uses this new knowledge to generate a final, conversational response in Vietnamese.
9. **Exit:** The router runs again, sees no new tool calls, routes to the exit node, and the final response is delivered back to the user via FastAPI.
