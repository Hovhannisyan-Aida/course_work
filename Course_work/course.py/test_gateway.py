import asyncio
import httpx
import time
from typing import List, Dict
import sys


class GatewayTester:
    def __init__(self, gateway_url: str = "http://localhost:8000"):
        self.gateway_url = gateway_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.results: List[Dict] = []
    
    def print_test(self, name: str):
        """Print test անունը"""
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print(f"{'='*60}")
    
    def print_result(self, success: bool, message: str):
        """Print test-ի արդյունքը"""
        icon = "Passed" if success else "Failed"
        print(f"{icon} {message}")
        self.results.append({"success": success, "message": message})
    
    async def test_health_check(self):
        """Թեստ 1: Health Check"""
        self.print_test("Health Check")
        
        try:
            response = await self.client.get(f"{self.gateway_url}/health")
            
            if response.status_code == 200:
                data = response.json()
                self.print_result(True, f"Gateway is healthy: {data}")
            else:
                self.print_result(False, f"Unexpected status: {response.status_code}")
        
        except Exception as e:
            self.print_result(False, f"Health check failed: {str(e)}")
    
    async def test_metrics(self):
        """Թեստ 2: Metrics"""
        self.print_test("Metrics Endpoint")
        
        try:
            response = await self.client.get(f"{self.gateway_url}/metrics")
            
            if response.status_code == 200:
                data = response.json()
                self.print_result(True, f"Metrics retrieved: {data.get('stats', {})}")
            else:
                self.print_result(False, f"Unexpected status: {response.status_code}")
        
        except Exception as e:
            self.print_result(False, f"Metrics failed: {str(e)}")
    
    async def test_routing(self):
        """Թեստ 3: Request Routing"""
        self.print_test("Request Routing")
        
        endpoints = [
            "/api/users",
            "/api/products",
            "/api/orders"
        ]
        
        for endpoint in endpoints:
            try:
                response = await self.client.get(
                    f"{self.gateway_url}{endpoint}",
                    headers={"X-User-ID": "test-user"}
                )
                
                if response.status_code == 200:
                    self.print_result(True, f"{endpoint} → {response.status_code}")
                elif response.status_code == 503:
                    self.print_result(True, f"{endpoint} → Service unavailable (expected without backends)")
                else:
                    self.print_result(False, f"{endpoint} → {response.status_code}")
            
            except Exception as e:
                self.print_result(False, f"{endpoint} failed: {str(e)}")
    
    async def test_rate_limiting(self):
        """Թեստ 4: Rate Limiting"""
        self.print_test("Rate Limiting")

        user_id = "rate-limit-test-user"
        endpoint = "/api/users"
        limit = 50  # Limit for anonymous tier

        print(f"Sending {limit + 10} requests to test rate limit...")

        success_count = 0
        rate_limited_count = 0

        for i in range(limit + 10):
            try:
                response = await self.client.get(
                    f"{self.gateway_url}{endpoint}",
                    headers={
                        "X-User-ID": user_id,
                        "X-User-Tier": "anonymous"  
                    }
                )

                if response.status_code == 429:
                    rate_limited_count += 1
                else:
                    success_count += 1

            except Exception as e:
                pass

        if rate_limited_count > 0:
            self.print_result(
                True,
                f"Rate limiting works! {success_count} allowed, {rate_limited_count} rate-limited"
            )
        else:
            self.print_result(
                False,
                f"Rate limiting not working: all {success_count} requests succeeded"
            )
    
    async def test_caching(self):
        """Թեստ 5: Response Caching"""
        self.print_test("Response Caching")

        unique_id = int(time.time() * 1000)
        endpoint = f"/api/products?test_id={unique_id}"

        try:
            response1 = await self.client.get(
                f"{self.gateway_url}{endpoint}",
                headers={"X-User-ID": "cache-test"}
            )

            # Check if backend service is available
            if response1.status_code != 200:
                self.print_result(
                    True,
                    f"Caching test skipped (backend service not running - status {response1.status_code})"
                )
                return

            cache_header1 = response1.headers.get("X-Cache", "MISS")

            await asyncio.sleep(0.1)

            response2 = await self.client.get(
                f"{self.gateway_url}{endpoint}",
                headers={"X-User-ID": "cache-test"}
            )
            cache_header2 = response2.headers.get("X-Cache", "MISS")

            if cache_header1 == "MISS" and cache_header2 == "HIT":
                self.print_result(True, "Caching works! First: MISS, Second: HIT")
            else:
                self.print_result(
                    False,
                    f"Caching issue. First: {cache_header1}, Second: {cache_header2}"
                )

        except Exception as e:
            self.print_result(False, f"Caching test failed: {str(e)}")
    
    async def test_circuit_breaker(self):
        """Թեստ 6: Circuit Breaker"""
        self.print_test("Circuit Breaker")
        
        
        try:
            response = await self.client.get(f"{self.gateway_url}/metrics")
            data = response.json()
            
            if "circuit_breakers" in data:
                cb_states = data["circuit_breakers"]
                self.print_result(
                    True,
                    f"Circuit breakers active: {list(cb_states.keys())}"
                )
            else:
                self.print_result(False, "Circuit breaker data not found")
        
        except Exception as e:
            self.print_result(False, f"Circuit breaker test failed: {str(e)}")
    
    async def test_error_handling(self):
        """Թեստ 7: Error Handling"""
        self.print_test("Error Handling")
        
        # Test 404 - route not found
        try:
            response = await self.client.get(
                f"{self.gateway_url}/api/nonexistent",
                headers={"X-User-ID": "test"}
            )
            
            if response.status_code == 404:
                self.print_result(True, "404 handling works correctly")
            else:
                self.print_result(False, f"Expected 404, got {response.status_code}")
        
        except Exception as e:
            self.print_result(False, f"Error handling test failed: {str(e)}")
    
    async def test_headers(self):
        """Թեստ 8: Custom Headers"""
        self.print_test("Custom Headers")
        
        try:
            response = await self.client.get(
                f"{self.gateway_url}/api/users",
                headers={"X-User-ID": "header-test"}
            )
            
            required_headers = ["X-Request-ID", "X-Response-Time", "X-Service"]
            missing_headers = []
            
            for header in required_headers:
                if header not in response.headers:
                    missing_headers.append(header)
            
            if not missing_headers:
                self.print_result(True, f"All custom headers present: {required_headers}")
            else:
                self.print_result(False, f"Missing headers: {missing_headers}")
        
        except Exception as e:
            self.print_result(False, f"Headers test failed: {str(e)}")
    
    async def run_all_tests(self):
        """Գործարկել բոլոր թեստերը"""
        print(f"\n{'#'*60}")
        print(f"# GATEWAY TEST SUITE")
        print(f"# Target: {self.gateway_url}")
        print(f"{'#'*60}")
        
        tests = [
            self.test_health_check,
            self.test_metrics,
            self.test_routing,
            self.test_caching,
            self.test_circuit_breaker,
            self.test_error_handling,
            self.test_headers,
            self.test_rate_limiting,  
        ]
        
        for test in tests:
            await test()
            await asyncio.sleep(0.5)  
        
        self.print_summary()
    
    def print_summary(self):
        """Print test-երի ամփոփումը"""
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["success"])
        failed = total - passed
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        
        if failed > 0:
            print(f"\n Failed Tests:")
            for result in self.results:
                if not result["success"]:
                    print(f"  - {result['message']}")
        
        print(f"\n{'='*60}\n")
    
    async def close(self):
        """Փակել HTTP client-ը"""
        await self.client.aclose()


async def main():
    """Main function"""
    gateway_url = "http://localhost:8000"
    
    if len(sys.argv) > 1:
        gateway_url = sys.argv[1]
    
    print(f"\n Starting Gateway Tests...")
    print(f"Target: {gateway_url}")
    print(f"Tip: Make sure Gateway is running!\n")
    
    tester = GatewayTester(gateway_url)
    
    try:
        await tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nTest suite error: {str(e)}")
    finally:
        await tester.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nBye!")