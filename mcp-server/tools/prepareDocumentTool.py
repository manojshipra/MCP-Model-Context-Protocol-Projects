import os
import requests
import sys
import threading
from mcp.server.fastmcp import FastMCP
import documentExtractor as de

# Create an MCP server instance.
mcp = FastMCP("Google-Search-MCP-Server")
SERPER_API_KEY = "e272470b8aebb46534713dc24393bd7832396b11"

def background_extraction(links):
    """
    Offload the document extraction and vectorstore creation to a background thread.
    """
    try:
        # Load documents from the links.
        documents, tokens_per_doc = de.load_langgraph_docs(links)
        # Save the documents to a file.
        de.save_llms_full(documents)
        # Split the documents as needed.
        split_docs = de.split_documents(documents)
        # Create the vector store for further processing.
        vectorstore = de.create_vectorstore(split_docs)
        # Optionally, you can log the result.
        print("Document extraction and vector store creation completed.")
    except Exception as e:
        print(f"Background extraction failed: {e}")

@mcp.tool()
def google_search_tool(query: str) -> str:
    """
    Query Google using the Serper API and return website links only.
    
    Args:
        query (str): The search query.
    
    Returns:
        str: A newline-separated string of website links from the organic results.
    """
    url = "https://google.serper.dev/search"
    params = {"q": query, "api_key": SERPER_API_KEY}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except Exception as e:
        return f"Error while calling Serper API: {e}"
    
    data = response.json()
    
    # Extract website links from organic search results.
    organic_results = data.get("organic", [])
    links = [result.get("link", "") for result in organic_results if result.get("link")]
    if(len(links)>=3):
        links=links[:3]
    
    if not links:
        return "No website links found for the query."
    
    # Spawn a background thread to run document extraction.
    extraction_thread = threading.Thread(target=background_extraction, args=(links,))
    extraction_thread.daemon = True  # Mark thread as daemon so it exits when the main process does.
    extraction_thread.start()
    
    # Immediately return the links.
    return "\n".join(links)

if __name__ == "__main__":
    # Initialize and run the MCP server using stdio transport.
    mcp.run(transport='stdio')