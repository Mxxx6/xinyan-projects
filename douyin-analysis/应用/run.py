#!/usr/bin/env python3
"""Development server entry point."""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="抖音数据分析仪表盘")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--reload", action="store_true", default=True, help="Auto-reload")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
