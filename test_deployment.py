"""
BrandFlow 배포 상태 검토 스크립트
로컬 환경에서 모든 기능을 테스트하여 배포 준비 상태를 확인
"""

import asyncio
import aiohttp
import time
import json
from datetime import datetime

class DeploymentTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "base_url": base_url,
            "tests": {},
            "summary": {}
        }
    
    async def test_health_check(self, session):
        """기본 헬스체크"""
        try:
            async with session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    self.results["tests"]["health_check"] = {
                        "status": "PASS",
                        "response": data,
                        "response_time": response.headers.get('X-Response-Time', 'N/A')
                    }
                    print("✅ Health Check: PASS")
                    return True
                else:
                    self.results["tests"]["health_check"] = {
                        "status": "FAIL",
                        "error": f"HTTP {response.status}"
                    }
                    print(f"❌ Health Check: FAIL (HTTP {response.status})")
                    return False
        except Exception as e:
            self.results["tests"]["health_check"] = {
                "status": "ERROR",
                "error": str(e)
            }
            print(f"❌ Health Check: ERROR - {e}")
            return False
    
    async def test_api_docs(self, session):
        """API 문서 접근 테스트"""
        try:
            async with session.get(f"{self.base_url}/docs") as response:
                if response.status == 200:
                    self.results["tests"]["api_docs"] = {
                        "status": "PASS",
                        "url": f"{self.base_url}/docs"
                    }
                    print("✅ API Documentation: PASS")
                    return True
                else:
                    self.results["tests"]["api_docs"] = {
                        "status": "FAIL",
                        "error": f"HTTP {response.status}"
                    }
                    print(f"❌ API Documentation: FAIL")
                    return False
        except Exception as e:
            self.results["tests"]["api_docs"] = {
                "status": "ERROR",
                "error": str(e)
            }
            print(f"❌ API Documentation: ERROR - {e}")
            return False
    
    async def test_api_endpoints(self, session):
        """핵심 API 엔드포인트 테스트"""
        endpoints = [
            "/api/campaigns/",
            "/api/purchase-requests/",
            "/api/users/",
            "/api/websocket/connections/stats",
            "/api/files/info",
            "/api/export/files",
            "/api/search/fields/campaigns",
            "/api/performance-dashboard/metrics",
            "/api/security-dashboard/summary"
        ]
        
        passed = 0
        total = len(endpoints)
        
        for endpoint in endpoints:
            try:
                async with session.get(f"{self.base_url}{endpoint}") as response:
                    # 인증이 필요한 엔드포인트는 401이 정상
                    if response.status in [200, 401]:
                        print(f"✅ {endpoint}: PASS (HTTP {response.status})")
                        passed += 1
                    else:
                        print(f"❌ {endpoint}: FAIL (HTTP {response.status})")
            except Exception as e:
                print(f"❌ {endpoint}: ERROR - {e}")
        
        self.results["tests"]["api_endpoints"] = {
            "status": "PASS" if passed == total else "PARTIAL",
            "passed": passed,
            "total": total,
            "success_rate": f"{passed/total*100:.1f}%"
        }
        
        return passed > 0
    
    async def test_websocket_connection(self):
        """WebSocket 연결 테스트"""
        try:
            import websockets
            
            # WebSocket 연결 시도 (토큰 없이 - 실패 예상)
            uri = f"ws://localhost:8000/api/websocket/ws"
            
            try:
                async with websockets.connect(uri) as websocket:
                    print("✅ WebSocket: Connection possible")
                    self.results["tests"]["websocket"] = {
                        "status": "PASS",
                        "message": "WebSocket server is running"
                    }
                    return True
            except websockets.exceptions.ConnectionClosedError as e:
                if "Authentication required" in str(e) or "policy violation" in str(e).lower():
                    print("✅ WebSocket: Server running (Authentication required as expected)")
                    self.results["tests"]["websocket"] = {
                        "status": "PASS",
                        "message": "WebSocket server is running with proper authentication"
                    }
                    return True
                else:
                    raise e
                    
        except ImportError:
            print("⚠️  WebSocket: websockets library not available for testing")
            self.results["tests"]["websocket"] = {
                "status": "SKIP",
                "message": "websockets library not available"
            }
            return True
        except Exception as e:
            print(f"❌ WebSocket: ERROR - {e}")
            self.results["tests"]["websocket"] = {
                "status": "ERROR",
                "error": str(e)
            }
            return False
    
    async def test_database_connection(self):
        """데이터베이스 연결 테스트"""
        try:
            from app.db.database import AsyncSessionLocal
            from sqlalchemy import text
            
            async with AsyncSessionLocal() as session:
                # 간단한 쿼리 실행
                result = await session.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    print("✅ Database: Connection successful")
                    self.results["tests"]["database"] = {
                        "status": "PASS",
                        "message": "Database connection successful"
                    }
                    return True
                else:
                    raise Exception("Query returned unexpected result")
                    
        except Exception as e:
            print(f"❌ Database: ERROR - {e}")
            self.results["tests"]["database"] = {
                "status": "ERROR",
                "error": str(e)
            }
            return False
    
    async def test_file_system(self):
        """파일 시스템 접근 테스트"""
        import os
        from pathlib import Path
        
        test_dirs = [
            "uploads",
            "exports", 
            "logs",
            "data"
        ]
        
        passed = 0
        for dir_name in test_dirs:
            dir_path = Path(dir_name)
            try:
                dir_path.mkdir(exist_ok=True)
                # 테스트 파일 쓰기
                test_file = dir_path / "test.txt"
                test_file.write_text("test")
                test_file.unlink()  # 삭제
                
                print(f"✅ Directory {dir_name}: PASS")
                passed += 1
            except Exception as e:
                print(f"❌ Directory {dir_name}: ERROR - {e}")
        
        self.results["tests"]["file_system"] = {
            "status": "PASS" if passed == len(test_dirs) else "PARTIAL",
            "passed": passed,
            "total": len(test_dirs)
        }
        
        return passed > 0
    
    async def run_all_tests(self):
        """모든 테스트 실행"""
        print("🚀 Starting BrandFlow Deployment Testing...")
        print("=" * 50)
        
        start_time = time.time()
        
        # 파일 시스템 테스트 (동기)
        print("\n📁 Testing File System...")
        fs_result = await self.test_file_system()
        
        # 데이터베이스 테스트 (동기)
        print("\n🗄️  Testing Database...")
        db_result = await self.test_database_connection()
        
        # HTTP 테스트 (비동기)
        print("\n🌐 Testing HTTP Endpoints...")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            health_result = await self.test_health_check(session)
            docs_result = await self.test_api_docs(session)
            api_result = await self.test_api_endpoints(session)
        
        # WebSocket 테스트
        print("\n🔌 Testing WebSocket...")
        ws_result = await self.test_websocket_connection()
        
        # 결과 요약
        end_time = time.time()
        test_duration = end_time - start_time
        
        all_results = [health_result, docs_result, api_result, ws_result, db_result, fs_result]
        passed_tests = sum(all_results)
        total_tests = len(all_results)
        
        self.results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "success_rate": f"{passed_tests/total_tests*100:.1f}%",
            "test_duration": f"{test_duration:.2f}s",
            "overall_status": "PASS" if passed_tests >= total_tests * 0.8 else "FAIL"
        }
        
        print("\n" + "=" * 50)
        print("📊 Test Summary:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Failed: {total_tests - passed_tests}")
        print(f"   Success Rate: {passed_tests/total_tests*100:.1f}%")
        print(f"   Duration: {test_duration:.2f}s")
        print(f"   Overall Status: {'✅ PASS' if passed_tests >= total_tests * 0.8 else '❌ FAIL'}")
        
        # 결과 파일로 저장
        with open("deployment_test_results.json", "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📋 Detailed results saved to: deployment_test_results.json")
        
        return self.results

async def main():
    """메인 테스트 실행"""
    print("BrandFlow Deployment Testing Tool")
    print("Testing local development environment...")
    
    tester = DeploymentTester()
    results = await tester.run_all_tests()
    
    return results

if __name__ == "__main__":
    asyncio.run(main())