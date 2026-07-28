#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Web 管理端入口：uvicorn 启动 FastAPI。"""

from __future__ import annotations

import argparse
import sys

from work_report.config import ROOT_DIR


def main() -> int:
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    parser = argparse.ArgumentParser(description="启动周报管理 Web 服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="开发热重载")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "work_report.api:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
