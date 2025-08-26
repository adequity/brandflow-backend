"""
모니터링 시스템 테스트 스크립트
"""

import requests
import json
import time

# API 기본 URL
API_BASE = "http://127.0.0.1:8003"

def test_monitoring_endpoints():
    """모니터링 엔드포인트 테스트"""
    print("=== BrandFlow 모니터링 시스템 테스트 ===")
    
    # 1. 관리자 로그인
    print("\n1. 관리자 로그인...")
    login_response = requests.post(f"{API_BASE}/api/auth/login-json", json={
        "email": "admin@test.com",
        "password": "Admin123!"
    })
    
    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("로그인 성공")
    else:
        print("로그인 실패")
        return
    
    # 2. 헬스 체크 (인증 불필요)
    print("\n2. 헬스 체크...")
    health_response = requests.get(f"{API_BASE}/api/monitoring/health")
    if health_response.status_code == 200:
        health_data = health_response.json()
        print(f"시스템 상태: {health_data['status']}")
        print(f"   업타임: {health_data['uptime']:.1f}초")
        print(f"   CPU: {health_data['checks']['cpu']['value']:.1f}%")
        print(f"   메모리: {health_data['checks']['memory']['value']:.1f}%")
    else:
        print(f"헬스 체크 실패: {health_response.status_code}")
    
    # 3. 시스템 통계
    print("\n3. 시스템 통계 조회...")
    stats_response = requests.get(f"{API_BASE}/api/monitoring/system", headers=headers)
    if stats_response.status_code == 200:
        stats_data = stats_response.json()
        print(f"전체 요청 수: {stats_data['requests']['total']}")
        print(f"   성공률: {stats_data['requests']['success_rate']:.1f}%")
        print(f"   활성 요청: {stats_data['requests']['active']}")
    else:
        print(f"시스템 통계 실패: {stats_response.status_code}")
    
    # 4. 대시보드 데이터
    print("\n4. 모니터링 대시보드...")
    dashboard_response = requests.get(f"{API_BASE}/api/monitoring/dashboard", headers=headers)
    if dashboard_response.status_code == 200:
        dashboard_data = dashboard_response.json()
        print(f"시스템 상태: {dashboard_data['status']}")
        print(f"   평균 응답시간: {dashboard_data['requests']['avg_response_time']}ms")
        print(f"   CPU: {dashboard_data['system']['cpu']:.1f}%")
        print(f"   메모리: {dashboard_data['system']['memory']:.1f}%")
    else:
        print(f"대시보드 실패: {dashboard_response.status_code}")
    
    # 5. 요청 로그 조회
    print("\n5. 요청 로그 조회...")
    logs_response = requests.get(f"{API_BASE}/api/monitoring/requests?limit=5", headers=headers)
    if logs_response.status_code == 200:
        logs_data = logs_response.json()
        print(f"최근 요청 로그: {logs_data['total']}개")
        for log in logs_data['logs'][-3:]:  # 최근 3개만 표시
            duration_ms = log.get('duration', 0) * 1000
            print(f"   {log['method']} {log['url']} -> {log.get('status_code', 'N/A')} ({duration_ms:.1f}ms)")
    else:
        print(f"요청 로그 실패: {logs_response.status_code}")
    
    # 6. 알림 조회
    print("\n6. 시스템 알림 조회...")
    alerts_response = requests.get(f"{API_BASE}/api/monitoring/alerts", headers=headers)
    if alerts_response.status_code == 200:
        alerts_data = alerts_response.json()
        print(f"시스템 알림: {alerts_data['total']}개")
        if alerts_data['alerts']:
            for alert in alerts_data['alerts'][-2:]:  # 최근 2개만 표시
                print(f"   [{alert['level']}] {alert['message']}")
        else:
            print("   현재 활성 알림 없음")
    else:
        print(f"알림 조회 실패: {alerts_response.status_code}")
    
    # 7. 에러 로그 조회
    print("\n7. 에러 로그 조회...")
    errors_response = requests.get(f"{API_BASE}/api/monitoring/errors", headers=headers)
    if errors_response.status_code == 200:
        errors_data = errors_response.json()
        print(f"에러 로그: {errors_data['total']}개")
        if errors_data['errors']:
            for error in errors_data['errors'][-2:]:  # 최근 2개만 표시
                print(f"   [{error['error_type']}] {error['error_message']}")
        else:
            print("   현재 에러 없음")
    else:
        print(f"에러 로그 실패: {errors_response.status_code}")
    
    print("\n=== 모니터링 시스템 테스트 완료 ===")


if __name__ == "__main__":
    test_monitoring_endpoints()