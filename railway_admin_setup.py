#!/usr/bin/env python3
"""
Railway 실배포 환경에 슈퍼어드민 계정을 직접 생성하는 스크립트
PostgreSQL 데이터베이스에 직접 연결해서 사용자와 캠페인을 생성
"""

import psycopg2
import bcrypt
from datetime import datetime
import os

# Railway PostgreSQL 연결 정보
RAILWAY_DB_URL = "postgresql://postgres:pASSWORD@autorack.proxy.rlwy.net:51902/railway"

def hash_password(password: str) -> str:
    """비밀번호 해시 생성"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_superadmin_on_railway():
    """Railway PostgreSQL에 슈퍼어드민 직접 생성"""
    
    try:
        # PostgreSQL 연결
        conn = psycopg2.connect(RAILWAY_DB_URL)
        cursor = conn.cursor()
        
        print("✅ Railway PostgreSQL 연결 성공")
        
        # 기존 사용자 확인
        cursor.execute("SELECT COUNT(*) FROM users WHERE email = %s", ('admin@brandflow.com',))
        existing_user = cursor.fetchone()[0]
        
        if existing_user > 0:
            print("⚠️ 슈퍼어드민이 이미 존재합니다")
            cursor.execute("SELECT id, name, email, role FROM users WHERE email = %s", ('admin@brandflow.com',))
            user = cursor.fetchone()
            print(f"기존 사용자: ID={user[0]}, 이름={user[1]}, 이메일={user[2]}, 역할={user[3]}")
            user_id = user[0]
        else:
            # 슈퍼어드민 생성
            admin_password = hash_password("admin123")
            
            insert_user_sql = """
                INSERT INTO users (name, email, hashed_password, role, company, contact, created_at, updated_at, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            now = datetime.now()
            cursor.execute(insert_user_sql, (
                "시스템 관리자",
                "admin@brandflow.com", 
                admin_password,
                "슈퍼 어드민",
                "BrandFlow",
                "02-1234-5678",
                now,
                now,
                True
            ))
            
            user_id = cursor.fetchone()[0]
            print(f"✅ 슈퍼어드민 생성 완료: ID={user_id}")
        
        # 기존 캠페인 확인
        cursor.execute("SELECT COUNT(*) FROM campaigns")
        campaign_count = cursor.fetchone()[0]
        
        if campaign_count == 0:
            # 테스트 캠페인 생성
            campaigns = [
                ("1212 - Updated Successfully", "수정 테스트용 캠페인", "클라이언트회사", 1000000, "진행중"),
                ("테스트 캠페인 2", "두 번째 테스트 캠페인", "클라이언트회사", 2000000, "준비중"),
                ("테스트 캠페인 3", "세 번째 테스트 캠페인", "클라이언트회사", 1500000, "진행중"),
                ("테스트 캠페인 4", "네 번째 테스트 캠페인", "클라이언트회사", 3000000, "완료")
            ]
            
            insert_campaign_sql = """
                INSERT INTO campaigns (name, description, client_company, budget, status, creator_id, created_at, updated_at, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            for name, desc, company, budget, status in campaigns:
                cursor.execute(insert_campaign_sql, (
                    name, desc, company, budget, status, user_id, now, now, now, now
                ))
            
            print(f"✅ {len(campaigns)}개 테스트 캠페인 생성 완료")
        else:
            print(f"⚠️ 캠페인이 이미 {campaign_count}개 존재합니다")
        
        # 변경사항 저장
        conn.commit()
        
        # 생성된 데이터 확인
        cursor.execute("SELECT id, name, email, role FROM users WHERE role = '슈퍼 어드민'")
        admins = cursor.fetchall()
        print("\n=== 슈퍼 어드민 계정 ===")
        for admin in admins:
            print(f"ID: {admin[0]}, 이름: {admin[1]}, 이메일: {admin[2]}, 역할: {admin[3]}")
        
        cursor.execute("SELECT id, name, status FROM campaigns ORDER BY id")
        campaigns = cursor.fetchall()
        print(f"\n=== 캠페인 목록 ({len(campaigns)}개) ===")
        for campaign in campaigns:
            print(f"ID: {campaign[0]}, 이름: {campaign[1]}, 상태: {campaign[2]}")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎉 Railway 실배포 환경 데이터 설정 완료!")
        print("계정 정보:")
        print("- 이메일: admin@brandflow.com")
        print("- 비밀번호: admin123")
        print("- 역할: 슈퍼 어드민")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        if conn:
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    create_superadmin_on_railway()