import sys
import io
import traceback
import asyncio
import subprocess
from mcp.server.fastmcp import FastMCP

e = FastMCP("python-executor-tool")

@e.tool()
async def execute_code(code: str) -> dict[str, str]:
    """
    Execute a Python code snippet, auto-install missing dependencies, and return output.

    Args:
        code: The Python code to execute as a single string.

    Returns:
        A dict with keys 'stdout' and 'stderr'.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_code_with_deps, code)


def _run_code_with_deps(code: str) -> dict[str, str]:
    """
    Helper that captures stdout/stderr, installs missing packages,
    and retries execution without user interruption.
    """
    # Capture outputs
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
    try:
        attempts = 0
        while True:
            attempts += 1
            try:
                # Execute user code in isolated globals
                exec(code, {})
                break  # success
            except ModuleNotFoundError as imp_err:
                pkg = imp_err.name
                # Auto-install missing package
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", pkg],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except subprocess.CalledProcessError as pip_err:
                    # pip install failed; include pip stderr and abort
                    sys.stderr.write(pip_err.stderr.decode(errors='ignore'))
                    break
                # retry exec after install
                continue
        # Return captured stdout and stderr
        return {"stdout": sys.stdout.getvalue(), "stderr": sys.stderr.getvalue()}
    except Exception:
        # Unexpected error: return traceback
        return {"stdout": sys.stdout.getvalue(), "stderr": traceback.format_exc()}
    finally:
        # Restore original streams
        sys.stdout, sys.stderr = old_out, old_err

if __name__ == "__main__":
    # Run over stdio transport
    e.run(transport="stdio")
