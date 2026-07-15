"""
SQL Agent - Natural Language to SQL Engine

Entry point for the FastAPI application.
"""
from __future__ import annotations

import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

logging.basicConfig(
     level=logging.INFO,
     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
     """Create and configure the FastAPI application"""
     app = FastAPI(
         title="SQL Agent API",
         description="Natural Language to SQL Engine",
         version="0.1.0",
     )

     # CORS
     app.add_middleware(
         CORSMiddleware,
         allow_origins=["*"],
         allow_credentials=True,
         allow_methods=["*"],
         allow_headers=["*"],
     )

     # Import and include routes
     from sql_agent.api.routes import router
     app.include_router(router)

     @app.get("/")
     async def root():
         return {
             "service": "SQL Agent",
             "version": "0.1.0",
             "docs": "/docs",
         }

     return app


app = create_app()


if __name__ == "__main__":
     host = os.getenv("HOST", "0.0.0.0")
     port = int(os.getenv("PORT", "8000"))
     logger.info(f"Starting SQL Agent on {host}:{port}")
     uvicorn.run("main:app", host=host, port=port, reload=True)
