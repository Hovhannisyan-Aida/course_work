from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
from typing import Optional, Dict, Any
import time
import logging
from contextlib import asynccontextmanager


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GatewayConfig:
    SERVICES = {
        'users': {
            'url': 'http://localhost:8001',
            'timeout': 10,
            'health_path': '/health'
        },
        'products': {
            'url': 'http://localhost:8002',
            'timeout': 15,
            'health_path': '/health'
        },
        'orders': {
            'url': 'http://localhost:8003',
            'timeout': 20,
            'health_path': '/health'
        }
    }
    
    ROUTES = {
        '/api/users': 'users',
        '/api/products': 'products',
        '/api/orders': 'orders'
    }
    
    RATE_LIMITS = {
        'default': 100,
        'anonymous': 50,
        'premium': 1000
    }
    
    CIRCUIT_BREAKER = {
        'failure_threshold': 5,
        'timeout': 60,
        'half_open_timeout': 30
    }


class InMemoryStorage:
    
    def __init__(self):
        self.rate_limits: Dict[str, Dict] = {}
        
        self.circuit_breakers: Dict[str, Dict] = {}
        
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cached_requests': 0
        }
    
    def get_rate_limit_data(self, key: str) -> Dict:
        current_time = time.time()
        
        if key not in self.rate_limits:
            self.rate_limits[key] = {
                'count': 0,
                'reset_time': current_time + 60
            }
        
        data = self.rate_limits[key]
        
        # Reset եթե ժամանակը անցել է
        if current_time > data['reset_time']:
            data['count'] = 0
            data['reset_time'] = current_time + 60
        
        return data
    
    def increment_rate_limit(self, key: str) -> int:
        """Ավելացնել rate limit counter-ը"""
        data = self.get_rate_limit_data(key)
        data['count'] += 1
        return data['count']
    
    def get_circuit_breaker_state(self, service: str) -> Dict:
        """Circuit breaker վիճակ"""
        if service not in self.circuit_breakers:
            self.circuit_breakers[service] = {
                'state': 'closed',  # closed, open, half-open
                'failures': 0,
                'last_failure_time': 0,
                'success_count': 0
            }
        return self.circuit_breakers[service]
    
    def cache_set(self, key: str, value: Any, ttl: int = 300):
        """Cache-ավորել արժեքը"""
        self.cache[key] = {
            'value': value,
            'expires_at': time.time() + ttl
        }
    
    def cache_get(self, key: str) -> Optional[Any]:
        """Վերադարձնել cache-ից"""
        if key not in self.cache:
            return None
        
        cached = self.cache[key]
        
        # Ստուգել TTL-ը
        if time.time() > cached['expires_at']:
            del self.cache[key]
            return None
        
        return cached['value']


class APIGateway:
    """Gateway-ի հիմնական տրամաբանություն"""
    
    def __init__(self, config: GatewayConfig, storage: InMemoryStorage):
        self.config = config
        self.storage = storage
        self.http_client = httpx.AsyncClient(timeout=30.0)
        logger.info("Gateway initialized")

    def find_service(self, path: str) -> Optional[str]:
        """Գտնել ծառայությունը path-ի հիման վրա"""
        for route_prefix, service_name in self.config.ROUTES.items():
            if path.startswith(route_prefix):
                return service_name
        return None
    
    def check_rate_limit(self, user_id: str, tier: str = 'default') -> bool:
        """Ստուգել rate limit-ը"""
        limit = self.config.RATE_LIMITS.get(tier, self.config.RATE_LIMITS['default'])
        count = self.storage.increment_rate_limit(user_id)
        
        if count > limit:
            logger.warning(f"Rate limit exceeded for {user_id}: {count}/{limit}")
            return False
        
        return True
    
    def check_circuit_breaker(self, service_name: str) -> bool:
        """Ստուգել circuit breaker-ը"""
        cb_state = self.storage.get_circuit_breaker_state(service_name)
        current_time = time.time()
        
        if cb_state['state'] == 'open':
            # Փորձել անցնել half-open-ի
            time_since_open = current_time - cb_state['last_failure_time']
            if time_since_open > self.config.CIRCUIT_BREAKER['timeout']:
                cb_state['state'] = 'half-open'
                cb_state['success_count'] = 0
                logger.info(f"Circuit breaker for {service_name}: OPEN -> HALF-OPEN")
                return True
            
            logger.warning(f"Circuit breaker OPEN for {service_name}")
            return False
        
        return True
    
    def record_success(self, service_name: str):
        """Գրանցել հաջող request-ը"""
        cb_state = self.storage.get_circuit_breaker_state(service_name)
        
        if cb_state['state'] == 'half-open':
            cb_state['success_count'] += 1
            if cb_state['success_count'] >= 2:
                cb_state['state'] = 'closed'
                cb_state['failures'] = 0
                logger.info(f"Circuit breaker for {service_name}: HALF-OPEN -> CLOSED")
        else:
            cb_state['failures'] = 0
        
        self.storage.stats['successful_requests'] += 1
    
    def record_failure(self, service_name: str):
        """Գրանցել ձախողված request-ը"""
        cb_state = self.storage.get_circuit_breaker_state(service_name)
        cb_state['failures'] += 1
        cb_state['last_failure_time'] = time.time()
        
        if cb_state['state'] == 'half-open':
            # Half-open-ում ցանկացած failure-ը բացում է circuit-ը
            cb_state['state'] = 'open'
            logger.warning(f"Circuit breaker for {service_name}: HALF-OPEN -> OPEN")
        elif cb_state['failures'] >= self.config.CIRCUIT_BREAKER['failure_threshold']:
            cb_state['state'] = 'open'
            logger.warning(f"Circuit breaker for {service_name}: CLOSED -> OPEN")
        
        self.storage.stats['failed_requests'] += 1
    
    async def forward_request(
        self,
        service_name: str,
        path: str,
        method: str,
        headers: dict,
        body: bytes = None,
        params: dict = None
    ) -> httpx.Response:
        """Forward անել request-ը backend-ին"""
        service_config = self.config.SERVICES[service_name]
        url = f"{service_config['url']}{path}"
        
        headers = {k: v for k, v in headers.items() 
                  if k.lower() not in ['host', 'connection', 'transfer-encoding']}
        
        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                headers=headers,
                content=body,
                params=params,
                timeout=service_config['timeout']
            )
            
            self.record_success(service_name)
            return response
            
        except httpx.TimeoutException:
            self.record_failure(service_name)
            raise HTTPException(status_code=504, detail=f"Gateway timeout: {service_name}")
        except httpx.ConnectError:
            self.record_failure(service_name)
            raise HTTPException(status_code=503, detail=f"Service unavailable: {service_name}")
        except Exception as e:
            self.record_failure(service_name)
            logger.error(f"Error forwarding to {service_name}: {str(e)}")
            raise HTTPException(status_code=502, detail=f"Bad gateway: {str(e)}")
    
    async def close(self):
        """Փակել HTTP client-ը"""
        await self.http_client.aclose()
        logger.info("Gateway closed")



storage = InMemoryStorage()
gateway = APIGateway(GatewayConfig(), storage)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle"""
    logger.info("Gateway starting...")
    yield
    logger.info("Gateway shutting down...")
    await gateway.close()


app = FastAPI(
    title="API Gateway",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_user_id(request: Request) -> str:
    """Extract user ID from request (պարզեցված տարբերակ)"""
    user_id = request.headers.get('X-User-ID', 'anonymous')
    return user_id


@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    """Գլխավոր middleware"""
    start_time = time.time()
    request_id = f"req-{int(start_time * 1000)}"
    
    # Logging
    logger.info(f"[{request_id}] {request.method} {request.url.path}")
    
    storage.stats['total_requests'] += 1
    
    try:
        # Եթե սա Gateway endpoint է, թույլ տալ
        if request.url.path in ['/health', '/metrics', '/docs', '/openapi.json']:
            return await call_next(request)
        
        service_name = gateway.find_service(request.url.path)
        
        if not service_name:
            logger.warning(f"[{request_id}] Route not found: {request.url.path}")
            duration = time.time() - start_time
            return JSONResponse(
                status_code=404,
                content={"error": "Route not found", "path": request.url.path},
                headers={
                    "X-Request-ID": request_id,
                    "X-Response-Time": f"{duration:.3f}s",
                    "X-Service": "none"
                }
            )
        
        user_id = request.headers.get('X-User-ID', 'anonymous')
        tier = request.headers.get('X-User-Tier', 'default')
        
        if not gateway.check_rate_limit(user_id, tier):
            duration = time.time() - start_time
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": 60
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-Response-Time": f"{duration:.3f}s",
                    "X-Service": service_name
                }
            )

        if not gateway.check_circuit_breaker(service_name):
            duration = time.time() - start_time
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service temporarily unavailable",
                    "service": service_name
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-Response-Time": f"{duration:.3f}s",
                    "X-Service": service_name
                }
            )
        
        if request.method == "GET":
            cache_key = f"{request.url.path}?{request.url.query}"
            cached_response = storage.cache_get(cache_key)

            if cached_response:
                storage.stats['cached_requests'] += 1
                duration = time.time() - start_time
                logger.info(f"[{request_id}] Cache HIT")
                return JSONResponse(
                    content=cached_response,
                    headers={
                        "X-Cache": "HIT",
                        "X-Request-ID": request_id,
                        "X-Response-Time": f"{duration:.3f}s",
                        "X-Service": service_name
                    }
                )
        
        # Forward request
        body = await request.body()
        
        response = await gateway.forward_request(
            service_name=service_name,
            path=request.url.path,
            method=request.method,
            headers=dict(request.headers),
            body=body if body else None,
            params=dict(request.query_params)
        )
        
        if request.method == "GET" and response.status_code == 200:
            cache_key = f"{request.url.path}?{request.url.query}"
            storage.cache_set(cache_key, response.json(), ttl=300)
        
        duration = time.time() - start_time
        logger.info(f"[{request_id}] {response.status_code} - {duration:.3f}s")
        
        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.content else None,
            headers={
                "X-Request-ID": request_id,
                "X-Response-Time": f"{duration:.3f}s",
                "X-Service": service_name,
                "X-Cache": "MISS"
            }
        )
    
    except HTTPException as e:
        duration = time.time() - start_time
        logger.error(f"[{request_id}] {e.status_code} - {e.detail}")
        return JSONResponse(
            status_code=e.status_code,
            content={"error": e.detail, "request_id": request_id},
            headers={
                "X-Request-ID": request_id,
                "X-Response-Time": f"{duration:.3f}s",
                "X-Service": service_name if 'service_name' in locals() else "unknown"
            }
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{request_id}] Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "request_id": request_id},
            headers={
                "X-Request-ID": request_id,
                "X-Response-Time": f"{duration:.3f}s",
                "X-Service": service_name if 'service_name' in locals() else "unknown"
            }
        )


@app.get("/health")
async def health_check():
    """Gateway առողջության ստուգում"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "services": list(GatewayConfig.SERVICES.keys())
    }


@app.get("/metrics")
async def get_metrics():
    """Gateway metrics"""
    return {
        "stats": storage.stats,
        "rate_limits": {
            k: v for k, v in storage.rate_limits.items()
        },
        "circuit_breakers": {
            k: {
                'state': v['state'],
                'failures': v['failures']
            }
            for k, v in storage.circuit_breakers.items()
        },
        "cache_size": len(storage.cache)
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "API Gateway",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    print("""
    ╔════════════════════════════════════════╗
    ║       API Gateway Starting...          ║
    ║                                        ║
    ║  Listening on: http://localhost:8000   ║
    ║  Docs: http://localhost:8000/docs      ║
    ║  Health: http://localhost:8000/health  ║
    ╚════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )