"""Entry point for running Mnemos as a module: python -m mnemos."""
import argparse

from mnemos.config import load_config
from mnemos.server import create_mcp_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Mnemos MCP Server")
    parser.add_argument("--vault", type=str, default=None, help="Path to Obsidian vault")
    args = parser.parse_args()

    config = load_config(args.vault)
    mcp = create_mcp_server(config)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
