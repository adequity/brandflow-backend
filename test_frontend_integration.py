#!/usr/bin/env python3
"""
Frontend-Backend Integration Test
프론트엔드와 백엔드 연동 테스트
"""

import requests
import json
import sys
from datetime import datetime

# Test configuration
FRONTEND_URL = "http://localhost:5174"  # Vite dev server
BACKEND_URL = "http://127.0.0.1:8001/api"  # FastAPI server

def test_cors_preflight():
    """CORS preflight 요청 테스트"""
    print("1. Testing CORS Preflight...")
    
    try:
        # OPTIONS 요청 (CORS preflight)
        response = requests.options(
            f"{BACKEND_URL}/auth/login",
            headers={
                'Origin': FRONTEND_URL,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'Content-Type'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"   [OK] CORS preflight successful")
            print(f"   Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin', 'Not set')}")
            print(f"   Access-Control-Allow-Methods: {response.headers.get('Access-Control-Allow-Methods', 'Not set')}")
            return True
        else:
            print(f"   [FAIL] CORS preflight failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   [ERROR] CORS test failed: {e}")
        return False

def test_login():
    """로그인 API 테스트"""
    print("2. Testing Login API...")
    
    try:
        # 로그인 요청 (생성된 어드민 계정 사용)
        login_data = {
            "username": "admin@test.com",
            "password": "AdminPassword123!"
        }
        
        response = requests.post(
            f"{BACKEND_URL}/auth/login",
            headers={
                'Origin': FRONTEND_URL,
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            data=login_data,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'access_token' in data:
                print(f"   [OK] Login successful")
                print(f"   Token type: {data.get('token_type', 'unknown')}")
                print(f"   User: {data.get('user', {}).get('name', 'unknown')}")
                return data['access_token']
            else:
                print(f"   [FAIL] Login response missing token")
                print(f"   Response: {data}")
                return None
        else:
            print(f"   [FAIL] Login failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"   [ERROR] Login test failed: {e}")
        return None

def test_authenticated_request(token):
    """인증된 API 요청 테스트"""
    print("3. Testing Authenticated API Request...")
    
    try:
        # 대시보드 요청 (인증 필요)
        response = requests.get(
            f"{BACKEND_URL}/dashboard/stats",
            headers={
                'Origin': FRONTEND_URL,
                'Authorization': f'Bearer {token}'
            },
            params={
                'viewerId': 2,
                'viewerRole': '슈퍼 어드민'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   [OK] Authenticated request successful")
            print(f"   Total campaigns: {data.get('total_campaigns', 'unknown')}")
            print(f"   User role: {data.get('user_role', 'unknown')}")
            return True
        else:
            print(f"   [FAIL] Authenticated request failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"   [ERROR] Authenticated request failed: {e}")
        return False

def test_dashboard_endpoints(token):
    """대시보드 엔드포인트 테스트"""
    print("4. Testing Dashboard Endpoints...")
    
    endpoints = [
        "/dashboard/charts",
        "/dashboard/analytics", 
        "/dashboard/summary"
    ]
    
    success_count = 0
    
    for endpoint in endpoints:
        try:
            response = requests.get(
                f"{BACKEND_URL}{endpoint}",
                headers={
                    'Origin': FRONTEND_URL,
                    'Authorization': f'Bearer {token}'
                },
                params={
                    'viewerId': 2,
                    'viewerRole': '슈퍼 어드민'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"   [OK] {endpoint}")
                success_count += 1
            else:
                print(f"   [FAIL] {endpoint}: {response.status_code}")
        except Exception as e:
            print(f"   [ERROR] {endpoint}: {e}")
    
    print(f"   Dashboard endpoints: {success_count}/{len(endpoints)} successful")
    return success_count == len(endpoints)

def main():
    """메인 테스트 함수"""
    print("=== FRONTEND-BACKEND INTEGRATION TEST ===")
    print()
    print(f"Frontend URL: {FRONTEND_URL}")
    print(f"Backend URL: {BACKEND_URL}")
    print()
    
    # 1. CORS 테스트
    cors_ok = test_cors_preflight()
    
    # 2. 로그인 테스트  
    token = test_login()
    
    # 3. 인증된 요청 테스트
    auth_ok = False
    dashboard_ok = False
    
    if token:
        auth_ok = test_authenticated_request(token)
        dashboard_ok = test_dashboard_endpoints(token)
    
    print()
    print("=== TEST SUMMARY ===")
    print(f"CORS Support: {'OK' if cors_ok else 'FAIL'}")
    print(f"Login API: {'OK' if token else 'FAIL'}")
    print(f"Authentication: {'OK' if auth_ok else 'FAIL'}")
    print(f"Dashboard APIs: {'OK' if dashboard_ok else 'FAIL'}")
    
    total_tests = 4
    passed_tests = sum([cors_ok, bool(token), auth_ok, dashboard_ok])
    
    print()
    print(f"Overall: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
    
    if passed_tests == total_tests:
        print()
        print("SUCCESS: Frontend-Backend integration is working properly!")
        print("Ready for production deployment.")
    else:
        print()
        print("WARNING: Some integration issues detected.")
        print("Check CORS settings, authentication, or API endpoints.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)