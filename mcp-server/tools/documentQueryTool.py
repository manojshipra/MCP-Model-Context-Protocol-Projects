

from mcp.server.fastmcp import FastMCP
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import SKLearnVectorStore
import os

# Define common path to the repo locally
PATH = "/Users/manojs/Documents/MCP_projects/MCP-Model-Context-Protocol-Projects/mcp-server/helper_functions/"
os.environ['OPENAI_API_KEY']="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"

# Create an MCP server
mcp = FastMCP("LangGraph-Docs-MCP-Server")

# Add a tool to query the LangGraph documentation
@mcp.tool()
def query_tool(query: str):
    """
    Query the website content using a retriever.
    
    Args:
        query (str): The query to search the documentation with


    Returns:
        str: A str of the retrieved documents
    """
    retriever = SKLearnVectorStore(
        embedding=OpenAIEmbeddings(model="text-embedding-3-large"), 
        persist_path=PATH + "sklearn_vectorstore.parquet", 
        serializer="parquet").as_retriever(search_kwargs={"k": 3}
        )

    relevant_docs = retriever.invoke(query)
    print(f"Retrieved {len(relevant_docs)} relevant documents")
    formatted_context = "\n\n".join([f"==DOCUMENT {i+1}==\n{doc.page_content}" for i, doc in enumerate(relevant_docs)])
    return formatted_context

# The @mcp.resource() decorator is meant to map a URI pattern to a function that provides the resource content
@mcp.resource("docs://langgraph/full")
def get_all_langgraph_docs() -> str:
    """
    This returns the content of the websites asked for in txt format .

    Args: None

    Returns:
        str: The contents of the website
    """

    # Local path to the LangGraph documentation
    doc_path = PATH + "llms_full.txt"
    try:
        with open(doc_path, 'r') as file:
            return file.read()
    except Exception as e:
        return f"Error reading log file: {str(e)}"

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')