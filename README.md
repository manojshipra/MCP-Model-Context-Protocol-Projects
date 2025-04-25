# MCP-Model-Context-Protocol-Projects

A multimodal assistant client built on the Model-Context-Protocol (MCP) framework, with tools for executing Python code, querying live weather via Server-Sent Events (SSE), and more.

## Table of Contents

- [Features](#features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
- [Usage](#usage)
  - [Run the Weather SSE Tool](#run-the-weather-sse-tool)
  - [Run the Streamlit UI](#run-the-streamlit-ui)
- [Requirements](#requirements)
- [License](#license)

## Features

- **Weather SSE Tool**: Connects to an MCP SSE server to stream live weather updates.
- **Streamlit Front End**: Interactive UI for sending queries to MCP servers.
- **Python Executor**: Tool for sandboxed execution of Python code via MCP.

## Getting Started

### Prerequisites

- Python 3.9 or later
- `pip` package manager
- A valid Groq API key

### Installation

1. Clone this repository:
3. Create and activate a virtual environment (optional but recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration

Create a `.env` file in the project root containing only your Groq API key:
create the .env file inside mcp-client folder.
```dotenv
GROQ_API_KEY=your_groq_api_key_here
```

## Usage

### Run the Weather SSE Tool

This tool connects to your MCP SSE server and prints live weather updates:
```bash
cd mcp-server
python3 weather.py
```

### Run the Streamlit UI

Launch the interactive front end for querying MCP servers:
```bash
cd mcp-client
streamlit run main.py
```

## Requirements

See [requirements.txt](requirements.txt).

## License

This project is licensed under the MIT License.

