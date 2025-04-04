from fastapi import FastAPI
from app.routes import webhook, send_message, websockets
from app.database import get_database

app = FastAPI()

# Routers principales
app.include_router(webhook.router)
app.include_router(send_message.router)
app.include_router(websockets.router)

# Ruta base
@app.get("/")
def root():
    return {"status": "running"}

@app.delete("/messages")
async def delete_all_messages():
    """
    Endpoint para eliminar todos los mensajes.
    """
    db = get_database()
    try:
        result = await db["messages"].delete_many({})
        return {
            "status": "success",
            "deleted_count": result.deleted_count
        }
    except Exception as e:
        print(e)

# Endpoint para verificar conexión a Mongo
@app.get("/health")
async def health_check():
    db = get_database()
    try:
        await db.command("ping")
        return {"status": "ok", "mongo": "connected"}
    except Exception as e:
        return {"status": "error", "mongo": str(e)}

# Test en startup
@app.on_event("startup")
async def test_mongo_connection():
    db = get_database()
    try:
        await db.command("ping")
        print("✅ Conectado a MongoDB correctamente")
    except Exception as e:
        print("❌ Error conectando a MongoDB:", e)