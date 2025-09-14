#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
from datetime import datetime, timedelta

RAILWAY_API_BASE = "https://brandflow-backend-production-99ae.up.railway.app"

def create_user_on_railway(user_data):
    url = f"{RAILWAY_API_BASE}/api/users/"
    
    try:
        response = requests.post(url, json=user_data, headers={
            "Content-Type": "application/json"
        })
        
        if response.status_code == 201:
            print(f"사용자 생성 성공: {user_data['email']}")
            return response.json()
        else:
            print(f"사용자 생성 실패: {user_data['email']} - {response.status_code}")
            print(f"응답: {response.text}")
            return None
            
    except Exception as e:
        print(f"오류: {e}")
        return None

def login_to_railway(email, password):
    url = f"{RAILWAY_API_BASE}/api/auth/login-json"
    
    login_data = {
        "email": email,
        "password": password
    }
    
    try:
        response = requests.post(url, json=login_data, headers={
            "Content-Type": "application/json"
        })
        
        if response.status_code == 200:
            result = response.json()
            print(f"로그인 성공: {email}")
            return result.get("access_token")
        else:
            print(f"로그인 실패: {email} - {response.status_code}")
            print(f"응답: {response.text}")
            return None
            
    except Exception as e:
        print(f"오류: {e}")
        return None

def create_campaign_on_railway(campaign_data, auth_token):
    url = f"{RAILWAY_API_BASE}/api/campaigns/"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }
    
    try:
        response = requests.post(url, json=campaign_data, headers=headers)
        
        if response.status_code == 201:
            print(f"캠페인 생성 성공: {campaign_data['name']}")
            return response.json()
        else:
            print(f"캠페인 생성 실패: {campaign_data['name']} - {response.status_code}")
            print(f"응답: {response.text}")
            return None
            
    except Exception as e:
        print(f"오류: {e}")
        return None

def main():
    print("Railway 데이터 마이그레이션 시작")
    
    # 1. 슈퍼 어드민 계정 생성
    super_admin = {
        "name": "시스템 관리자",
        "email": "admin@brandflow.com",
        "password": "admin123",
        "role": "슈퍼 어드민",
        "company": "BrandFlow",
        "contact": "02-1234-5678"
    }
    
    print("\n--- 슈퍼 어드민 계정 생성 ---")
    admin_result = create_user_on_railway(super_admin)
    
    # 2. 대행사 어드민 계정 생성
    agency_admin = {
        "name": "테스트 대행사 어드민",
        "email": "agency@testcompany.com",
        "password": "testpass123!",
        "role": "대행사 어드민",
        "company": "TestCompany",
        "contact": "02-2222-2222"
    }
    
    print("\n--- 대행사 어드민 계정 생성 ---")
    agency_result = create_user_on_railway(agency_admin)
    
    # 3. 클라이언트 계정 생성
    client_user = {
        "name": "클라이언트1",
        "email": "client1@company.com",
        "password": "client123",
        "role": "클라이언트",
        "company": "클라이언트회사",
        "contact": "02-4444-4444"
    }
    
    print("\n--- 클라이언트 계정 생성 ---")
    client_result = create_user_on_railway(client_user)
    
    # 4. 슈퍼 어드민으로 로그인
    print("\n--- 슈퍼 어드민 로그인 ---")
    auth_token = login_to_railway("admin@brandflow.com", "admin123")
    
    if not auth_token:
        print("로그인 실패로 캠페인 생성을 건너뜁니다")
        return
    
    # 5. 테스트 캠페인들 생성
    campaigns = [
        {
            "name": "1212 - Updated Successfully",
            "description": "수정 테스트용 캠페인",
            "client_company": "클라이언트회사",
            "budget": 1000000,
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() + timedelta(days=30)).isoformat(),
            "status": "진행중"
        },
        {
            "name": "테스트 캠페인 2",
            "description": "두 번째 테스트 캠페인",
            "client_company": "클라이언트회사",
            "budget": 2000000,
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() + timedelta(days=60)).isoformat(),
            "status": "준비중"
        },
        {
            "name": "테스트 캠페인 3",
            "description": "세 번째 테스트 캠페인",
            "client_company": "클라이언트회사",
            "budget": 1500000,
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() + timedelta(days=45)).isoformat(),
            "status": "진행중"
        },
        {
            "name": "테스트 캠페인 4",
            "description": "네 번째 테스트 캠페인",
            "client_company": "클라이언트회사",
            "budget": 3000000,
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() + timedelta(days=90)).isoformat(),
            "status": "완료"
        }
    ]
    
    print("\n--- 캠페인 생성 ---")
    for campaign in campaigns:
        create_campaign_on_railway(campaign, auth_token)
    
    print("\nRailway 데이터 마이그레이션 완료!")
    print("\n생성된 계정:")
    print("- admin@brandflow.com / admin123 (슈퍼 어드민)")
    print("- agency@testcompany.com / testpass123! (대행사 어드민)")
    print("- client1@company.com / client123 (클라이언트)")

if __name__ == "__main__":
    main()