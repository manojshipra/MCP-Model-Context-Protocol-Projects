import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from openai import OpenAI
from dotenv import load_dotenv
import json
import logging
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# OpenAI client setup
# client = OpenAI(
#     base_url='http://localhost:11434/v1',
#     api_key='ollama',  # required, but unused
# )
client = OpenAI(
    base_url='https://api.groq.com/openai/v1',
    api_key=os.getenv("GROQ_API_KEY"),  # required, but unused
    )


class ConnectionManager:
    def __init__(self, stdio_server_map, sse_server_map):
        self.stdio_server_map = stdio_server_map
        self.sse_server_map = sse_server_map
        self.sessions = {}
        self.exit_stack = AsyncExitStack()

    async def initialize(self):
        # Initialize stdio connections
        for server_name, params in self.stdio_server_map.items():
            try:
                logger.info(f"Connecting to stdio server: {server_name}")
                stdio_transport = await self.exit_stack.enter_async_context(
                    stdio_client(params)
                )
                read, write = stdio_transport
                session = await self.exit_stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                self.sessions[server_name] = session
                logger.info(f"Successfully connected to stdio server: {server_name}")
            except Exception as e:
                logger.error(f"Failed to connect to stdio server {server_name}: {e}")

        # Initialize SSE connections
        for server_name, url in self.sse_server_map.items():
            try:
                logger.info(f"Connecting to SSE server: {server_name} at {url}")
                sse_transport = await self.exit_stack.enter_async_context(
                    sse_client(url=url)
                )
                read, write = sse_transport
                session = await self.exit_stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                self.sessions[server_name] = session
                logger.info(f"Successfully connected to SSE server: {server_name}")
            except Exception as e:
                logger.error(f"Failed to connect to SSE server {server_name}: {e}")
                # Continue with other connections instead of failing completely

    async def list_tools(self):
        tool_map = {}
        consolidated_tools = []
        for server_name, session in self.sessions.items():
            try:
                tools = await session.list_tools()
                tool_map.update({tool.name: server_name for tool in tools.tools})
                consolidated_tools.extend(tools.tools)
                logger.info(f"Listed {len(tools.tools)} tools from {server_name}")
            except Exception as e:
                logger.error(f"Failed to list tools from {server_name}: {e}")
        return tool_map, consolidated_tools

    async def call_tool(self, tool_name, arguments, tool_map):
        server_name = tool_map.get(tool_name)
        if not server_name:
            logger.warning(f"Tool '{tool_name}' not found in tool map")
            return f"Error: Tool '{tool_name}' not found."

        session = self.sessions.get(server_name)
        if not session:
            logger.warning(f"No session available for server '{server_name}'")
            return f"Error: Server '{server_name}' is not connected."
        
        try:
            result = await session.call_tool(tool_name, arguments=arguments)
            return result.content[0].text
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return f"Error executing tool {tool_name}: {str(e)}"

    async def close(self):
        try:
            await self.exit_stack.aclose()
            logger.info("All connections closed successfully")
        except Exception as e:
            logger.error(f"Error while closing connections: {e}")


# Chat function to handle interactions and tool calls
async def chat(
    input_messages,
    tool_map,
    tools=[],
    max_turns=10,
    connection_manager=None,
):
    chat_messages = input_messages[:]
    for turn in range(max_turns):
        logger.info(f"Chat turn {turn+1}/{max_turns}")
        try:
            result = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=chat_messages,
                tools=tools if tools else None,
            )

            if result.choices[0].finish_reason == "tool_calls":
                chat_messages.append(result.choices[0].message)

                for tool_call in result.choices[0].message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    # Get server name for the tool just for logging
                    server_name = tool_map.get(tool_name, "Unknown server")

                    # Log tool call
                    log_message = f"**Tool Call**  \n**Tool Name:** `{tool_name}` from **MCP Server**: `{server_name}`  \n**Input:**  \n```json\n{json.dumps(tool_args, indent=2)}\n```"
                    yield {"role": "assistant", "content": log_message}

                    # Call the tool and log its observation
                    observation = await connection_manager.call_tool(
                        tool_name, tool_args, tool_map
                    )
                    log_message = f"**Tool Observation**  \n**Tool Name:** `{tool_name}` from **MCP Server**: `{server_name}`  \n**Output:**  \n```json\n{json.dumps(observation, indent=2)}\n```  \n---"
                    yield {"role": "assistant", "content": log_message}

                    chat_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(observation),
                        }
                    )
            else:
                yield {"role": "assistant", "content": result.choices[0].message.content}
                return
        except Exception as e:
            error_msg = f"Error during chat processing: {str(e)}"
            logger.error(error_msg)
            yield {"role": "assistant", "content": f"Sorry, I encountered an error: {str(e)}"}
            return

    # Generate a final response if max turns are reached
    try:
        result = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=chat_messages,
        )
        yield {"role": "assistant", "content": result.choices[0].message.content}
    except Exception as e:
        logger.error(f"Error generating final response: {e}")
        yield {"role": "assistant", "content": f"Sorry, I encountered an error in the final response: {str(e)}"}


# Filter and validate input schema for tools
def filter_input_schema(input_schema):
    if not isinstance(input_schema, dict):
        logger.warning(f"Invalid input schema: {input_schema}")
        return {"type": "object", "properties": {}, "required": []}
        
    if "properties" in input_schema:
        if "required" not in input_schema or not isinstance(
            input_schema["required"], list
        ):
            input_schema["required"] = list(input_schema["properties"].keys())
        else:
            for key in input_schema["properties"].keys():
                if key not in input_schema["required"]:
                    input_schema["required"].append(key)

        for key, value in input_schema["properties"].items():
            if "default" in value:
                del value["default"]

        if "additionalProperties" not in input_schema:
            input_schema["additionalProperties"] = False

    return input_schema


if __name__ == "__main__":
    # Define stdio and SSE server configurations
    stdio_server_map = {
        # "time_mcp": StdioServerParameters(
        #     command="uvx",
        #     args=[
        #         "mcp-server-time",
        #         "--local-timezone",
        #         "Asia/Kolkata",
        #     ],
        #     env=None,
        # ),
        "pythonExecutor": StdioServerParameters(
            command="python3",
            args=["../mcp-server/tools/pythonExecutorTool.py"],
            env=None,
        ),
    }

    sse_server_map = {
        "weather_sse": "http://localhost:8080/sse",
    }

    async def main():
        try:
            connection_manager = ConnectionManager(stdio_server_map, sse_server_map)
            await connection_manager.initialize()
            
            # Check if we have any valid connections
            if not connection_manager.sessions:
                logger.error("No MCP servers connected. Please check server availability.")
                return
                
            tool_map, tool_objects = await connection_manager.list_tools()
            
            if not tool_objects:
                logger.warning("No tools available from connected servers.")

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

            query = input("Enter your query: ")
            system_prompt="""You are operating in an agent loop, iteratively completing tasks through these steps:
1. Analyze Events...
2. Select Tools...
3. Wait for Execution...
4. Iterate: Choose only one tool call per iteration...
5. Submit Results...
6. Enter Standby..."""

            input_messages = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {"role": "user", "content": query},
            ]

            async for response in chat(
                input_messages,
                tool_map,
                tools=tools_json,
                connection_manager=connection_manager,
            ):
                print("\n------\n")
                print(f"RESPONSE: {response['role']}")
                print(response['content'])
                print("\n------\n")

        except Exception as e:
            logger.error(f"Main program error: {e}")
        finally:
            # Always try to close connections gracefully
            try:
                if 'connection_manager' in locals():
                    await connection_manager.close()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
   