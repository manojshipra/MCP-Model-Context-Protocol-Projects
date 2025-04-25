import streamlit as st 
import asyncio
import json

from openai_client import (
    chat,
    ConnectionManager,
    filter_input_schema,
    StdioServerParameters,
)

#Streamlit App title
st.title("MCP Client")

#Streamlit sidebar for configuration
st.sidebar.title("MCP server configurations")

#Input for stdio servers (JSON format)
stdio_servers = st.sidebar.text_area(
    "Stdio Servers (JSON format)",
    value=json.dumps(
        {
		  "time_mcp": {
		    "command": "uvx",
		    "args": [
		      "mcp-server-time",
		      "--local-timezone",
		      "Asia/Kolkata"
		    ]
		  },
		  "execute_code": {
		    "command": "python3",
		    "args": [
		      "../mcp-server/tools/pythonExecutorTool.py"
		    ]
		  }
		},
        indent=4,
    ),
)

# Input for SSE servers (JSON format)
sse_servers = st.sidebar.text_area(
    "SSE Servers (JSON format)",
    value=json.dumps(
        {"weather_sse": "http://localhost:8080/sse"},
        indent=4,
    ),
)

try:
    stdio_server_map = {
        name: StdioServerParameters(**params)
        for name, params in json.loads(stdio_servers).items()
    }
    sse_server_map = json.loads(sse_servers)
except json.JSONDecodeError:
    st.sidebar.error("Invalid JSON format in server configuration.")
    stdio_server_map, sse_server_map = {}, {}

# Initialize chat history if not already present
if "messages" not in st.session_state:
    system_message = """You are a sophisticated Large Language Model (LLM) assistant equipped with access to a variety of tools and SSE servers, each having a detailed description of its capabilities. Your role is to intelligently select and utilize these tools to effectively fulfill user requests, ensuring clarity and efficiency.

**Operational Guidelines:**

1. **Tool Selection and Usage:**
   - Evaluate user requests and select the most appropriate tool or server based on provided descriptions.
   - Clearly explain to the user your reasoning for selecting a specific tool before executing it.
   - Execute the tool precisely as per the provided tool schema.

2. **Communication:**
   - NEVER mention internal tool names directly to the user. Instead, explain actions in user-friendly language (e.g., instead of mentioning a specific tool, say "I will perform the required edit" or "I will fetch the necessary information").
   - Display the output from tools in a clear, concise, and human-readable format.

3. **Information Gathering:**
   - If unsure about fully meeting the user's request, proactively gather additional information by using relevant tools or asking clarifying questions.
   - Prefer self-sufficiency; avoid burdening the user with unnecessary clarification if you can independently resolve the ambiguity or uncertainty.

4. **Code Management:**
   - NEVER output raw code directly to the user unless explicitly requested.
   - Use code edit tools responsibly, limiting usage to at most one per turn.
   - Always ensure generated or edited code is immediately executable by the user by including all necessary imports, dependencies, and endpoints.
   - For new codebases, include clear dependency management files (e.g., `requirements.txt`) and comprehensive documentation (`README`).
   - For web applications, deliver a polished, modern UI adhering to high UX standards.
   - Avoid generating excessively long hashes or non-textual code that provides no practical value.
   - Ensure you fully understand existing code content before editing it.
   - If encountering linter errors, attempt corrections up to three iterations, then consult the user on further action.
   - Always store the code in a file with a relevant name and extension, ensuring the user can easily access and utilize it.

5. **General Conduct:**
   - Maintain clarity, accuracy, and efficiency in every interaction.
   - Prioritize providing complete and actionable solutions over partial answers.
   - Foster a helpful and seamless user experience through precise and proactive tool utilization.

"""
    st.session_state.messages = [{"role": "system", "content": system_message}]

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])

# Async function to handle chat and stream messages
async def handle_chat(connection_manager):
    # Fetch available tools from configured servers
    tool_map, tool_objects = await connection_manager.list_tools()
    tools_json = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "strict": True,
                "parameters": filter_input_schema(tool.inputSchema),
            },
        }
        for tool in tool_objects
    ]

    # Stream responses from the chat function
    async for response in chat(
        st.session_state.messages,
        tool_map,
        tools=tools_json,
        connection_manager=connection_manager,
    ):
        yield response


# React to user input
if user_message := st.chat_input("Your Message"):
    # Display user message in chat container
    st.chat_message("user").markdown(user_message)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_message})

    # Process assistant response
    with st.spinner("Assistant is typing..."):
        response_container = st.chat_message("assistant")

        async def stream_responses():
            # Initialize ConnectionManager
            connection_manager = ConnectionManager(stdio_server_map, sse_server_map)
            await connection_manager.initialize()

            try:
                # Stream assistant responses and update chat history
                async for response in handle_chat(connection_manager):
                    response_container.markdown(response["content"])
                    st.session_state.messages.append(response)
            finally:
                # Ensure connections are closed
                await connection_manager.close()

        asyncio.run(stream_responses())

