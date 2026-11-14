import asyncio
import logging
import api
from api import CellRef, RouteRequest

# Show DEBUG too, to demo per-vertex tracing.
logging.getLogger("traverse.routing").setLevel(logging.DEBUG)
logging.getLogger("traverse.api").setLevel(logging.DEBUG)

async def main():
    async with api.lifespan(api.app):
        from fastapi import Request
        scope = {"type": "http", "method": "POST", "path": "/route", "headers": [],
                 "query_string": b"", "client": ("127.0.0.1", 5000), "server": ("t", 80), "scheme": "http"}
        request = Request(scope)
        fn = api.post_route
        while hasattr(fn, "__wrapped__"):
            fn = fn.__wrapped__
        req = RouteRequest(waypoints=[CellRef(row=300, col=280), CellRef(row=302, col=282)])
        out = fn(request, req)
        print("RESULT reached:", out.reached, "legs:", len(out.legs), "cells:", out.path_cells)

asyncio.run(main())
