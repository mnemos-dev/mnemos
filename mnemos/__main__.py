"""Entry point for running Mnemos as a module: python -m mnemos."""
from mnemos.server import create_mcp_server


def main() -> None:
    mcp = create_mcp_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
