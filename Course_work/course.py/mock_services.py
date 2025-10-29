"""
Mock Backend Services
Թեստավորման համար պարզ backend ծառայություններ
"""

from fastapi import FastAPI
import uvicorn
import random
import time
import sys

def create_service(name: str, port: int):
    """Ստեղծել mock service"""
    app = FastAPI(title=f"{name} Service")
    
    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": name}
    
    @app.get(f"/api/{name}")
    async def list_items():
        # Simulate some processing time
        await asyncio.sleep(random.uniform(0.01, 0.1))
        
        return {
            "service": name,
            "data": [
                {"id": i, "name": f"{name.title()} {i}"}
                for i in range(1, 6)
            ],
            "timestamp": time.time()
        }
    
    @app.get(f"/api/{name}/{{item_id}}")
    async def get_item(item_id: int):
        # Simulate some processing time
        await asyncio.sleep(random.uniform(0.01, 0.1))
        
        # Randomly fail 10% of requests (to test circuit breaker)
        if random.random() < 0.1:
            raise Exception("Random service error")
        
        return {
            "service": name,
            "id": item_id,
            "name": f"{name.title()} {item_id}",
            "timestamp": time.time()
        }
    
    @app.post(f"/api/{name}")
    async def create_item(item: dict):
        await asyncio.sleep(random.uniform(0.01, 0.2))
        
        return {
            "service": name,
            "id": random.randint(1000, 9999),
            "created": item,
            "timestamp": time.time()
        }
    
    return app, port


# Create services
import asyncio

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mock_services.py [users|products|orders]")
        sys.exit(1)
    
    service_name = sys.argv[1]
    
    ports = {
        "users": 8001,
        "products": 8002,
        "orders": 8003
    }
    
    if service_name not in ports:
        print(f"Unknown service: {service_name}")
        print(f"Available: {', '.join(ports.keys())}")
        sys.exit(1)
    
    app, port = create_service(service_name, ports[service_name])
    
    print(f"""
    ╔════════════════════════════════════════╗
    ║   {service_name.upper()} Service Starting        ║
    ║                                        ║
    ║  Port: {port}                          ║
    ╚════════════════════════════════════════╝
    """)
    
    uvicorn.run(app, host="0.0.0.0", port=port)