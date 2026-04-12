"""Entry point for running Mnemos as a module: python -m mnemos.server"""
import sys


def main() -> None:
    # Parse --vault before heavy imports
    vault_path = None
    args = sys.argv[1:]
    if "--vault" in args:
        idx = args.index("--vault")
        if idx + 1 < len(args):
            vault_path = args[idx + 1]

    from mnemos.config import load_config
    config = load_config(vault_path)

    from mnemos.server import create_mcp_server
    mcp = create_mcp_server(config)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
