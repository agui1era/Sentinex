import os
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import httpx

# Cargar .env.server
load_dotenv(".env.server")

# Base URL de LM Studio (SIN /v1 !!!)
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL").rstrip("/")

# API KEY interna (puede ser cualquier string)
API_KEY = os.getenv("API_KEY", "12345")

app = FastAPI()


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(request: Request, path: str):

    # cuerpo crudo del request
    body = await request.body()

    # construir URL destino
    target_url = f"{LM_STUDIO_URL}/{path.lstrip('/')}"  # evita doble slash

    # headers a LM Studio
    headers = {
        "Content-Type": request.headers.get("Content-Type", "application/json"),
        "Authorization": f"Bearer {API_KEY}"
    }

    # cliente HTTP con timeout extendido
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.request(
                request.method,
                target_url,
                headers=headers,
                content=body
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Proxy error: {str(e)}"}
            )

    # retornar EXACTO lo que respondió LM Studio
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={"Content-Type": resp.headers.get("Content-Type", "application/json")}
    )