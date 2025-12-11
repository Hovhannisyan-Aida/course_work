# API Gateway Project

Production-ready API Gateway with rate limiting, circuit breaker, caching, and request routing.

## Features

- **Request Routing**: Routes requests to appropriate backend services
- **Rate Limiting**: Prevents API abuse with configurable limits per user tier
- **Circuit Breaker**: Protects against cascading failures
- **Response Caching**: Improves performance with intelligent caching
- **Health Checks**: Monitor gateway and service health
- **Metrics**: Real-time statistics and monitoring
- **Error Handling**: Comprehensive error handling and logging

## Project Structure

```
.
├── complete_gateway.py    # Main API Gateway application
├── mock_services.py       # Mock backend services for testing
├── test_gateway.py        # Automated test suite
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip

### Setup

1. **Install dependencies:**

```bash
pip install -r requirements.txt
```

## Usage

### Running the API Gateway

Start the gateway on port 8000:

```bash
python complete_gateway.py
```

The gateway will be available at:
- Main: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics

### Running Mock Backend Services

To test the gateway with mock backend services, open **3 separate terminals** and run:

**Terminal 1 - Users Service:**
```bash
python mock_services.py users
```

**Terminal 2 - Products Service:**
```bash
python mock_services.py products
```

**Terminal 3 - Orders Service:**
```bash
python mock_services.py orders
```

The services will run on:
- Users: http://localhost:8001
- Products: http://localhost:8002
- Orders: http://localhost:8003

### Running Tests

After starting the gateway (and optionally the mock services), run the test suite:

```bash
python test_gateway.py
```

Or specify a custom gateway URL:

```bash
python test_gateway.py http://localhost:8000
```

## API Endpoints

### Gateway Endpoints

- `GET /` - Root endpoint with service information
- `GET /health` - Health check
- `GET /metrics` - Gateway metrics and statistics
- `GET /docs` - Interactive API documentation

### Proxied Backend Routes

All requests to these paths are forwarded to backend services:

- `/api/users` → Users Service (port 8001)
- `/api/products` → Products Service (port 8002)
- `/api/orders` → Orders Service (port 8003)

## Configuration

Edit `complete_gateway.py` to customize configuration:

### Services Configuration

```python
SERVICES = {
    'users': {
        'url': 'http://localhost:8001',
        'timeout': 10,
        'health_path': '/health'
    },
    # Add more services...
}
```

### Rate Limiting

```python
RATE_LIMITS = {
    'default': 100,      # requests per minute
    'anonymous': 50,
    'premium': 1000
}
```

### Circuit Breaker

```python
CIRCUIT_BREAKER = {
    'failure_threshold': 5,
    'timeout': 60,
    'half_open_timeout': 30
}
```

## Custom Headers

The gateway supports these custom headers:

**Request Headers:**
- `X-User-ID`: User identifier (default: "anonymous")
- `X-User-Tier`: User tier for rate limiting (default, anonymous, premium)

**Response Headers:**
- `X-Request-ID`: Unique request identifier
- `X-Response-Time`: Request processing time
- `X-Service`: Backend service name
- `X-Cache`: Cache status (HIT/MISS)

## Example Requests

### Get Users List

```bash
curl -H "X-User-ID: user123" http://localhost:8000/api/users
```

### Get Product by ID

```bash
curl -H "X-User-ID: user123" http://localhost:8000/api/products/1
```

### Create Order

```bash
curl -X POST http://localhost:8000/api/orders \
  -H "X-User-ID: user123" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 2}'
```

### Check Metrics

```bash
curl http://localhost:8000/metrics
```

## Testing Different Features

### Test Rate Limiting

Send multiple requests quickly:

```bash
for i in {1..60}; do
  curl -H "X-User-ID: testuser" http://localhost:8000/api/users
done
```

You should see some requests get rate limited (HTTP 429).

### Test Caching

Make the same GET request twice:

```bash
curl -v http://localhost:8000/api/products
curl -v http://localhost:8000/api/products
```

The second request should have `X-Cache: HIT` header.

### Test Premium Tier

Use premium tier for higher rate limits:

```bash
curl -H "X-User-ID: premium-user" \
     -H "X-User-Tier: premium" \
     http://localhost:8000/api/users
```

## Monitoring

### View Real-time Metrics

```bash
curl http://localhost:8000/metrics
```

Response includes:
- Request statistics (total, successful, failed, cached)
- Rate limiting data per user
- Circuit breaker states
- Cache size

## Troubleshooting

### Gateway won't start

- Check if port 8000 is already in use
- Verify all dependencies are installed: `pip install -r requirements.txt`

### Service unavailable errors

- Ensure backend services are running (mock_services.py)
- Check service URLs in configuration match running services
- Verify services are healthy: `curl http://localhost:8001/health`

### Rate limiting not working

- Check that you're sending `X-User-ID` header
- Verify rate limit configuration
- Check metrics endpoint for current rate limit counts

### All requests fail

- Check gateway logs for detailed error messages
- Verify network connectivity to backend services
- Check circuit breaker states in metrics

## Development

### Adding a New Service

1. Add service configuration in `SERVICES`:

```python
'newservice': {
    'url': 'http://localhost:8004',
    'timeout': 10,
    'health_path': '/health'
}
```

2. Add route mapping in `ROUTES`:

```python
'/api/newservice': 'newservice'
```

3. Restart the gateway

### Customizing Behavior

- **Caching TTL**: Modify `storage.cache_set(key, value, ttl=300)` in line 391
- **Timeout**: Change service timeout in `SERVICES` configuration
- **Logging**: Adjust logging level in line 17

## License

This is a course project for educational purposes.

## Support

For issues or questions, please check the logs and metrics endpoint for debugging information.
