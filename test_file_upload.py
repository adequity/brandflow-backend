"""
파일 업로드 기능 테스트
"""

import asyncio
import requests
from pathlib import Path

API_BASE = "http://127.0.0.1:8003"

async def test_file_upload():
    """파일 업로드 기능 테스트"""
    
    print("파일 업로드 기능 테스트 시작...")
    
    # 1. 로그인으로 토큰 획득
    login_response = requests.post(f"{API_BASE}/api/auth/login-json", json={
        "email": "admin@test.com",
        "password": "Admin123!"
    })
    
    if login_response.status_code != 200:
        print(f"로그인 실패: {login_response.status_code}")
        return
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    print("로그인 성공")
    
    # 2. 업로드 정보 조회
    info_response = requests.get(f"{API_BASE}/api/files/info")
    
    if info_response.status_code == 200:
        info = info_response.json()
        print(f"허용된 파일 형식: {info['allowed_extensions']}")
        print(f"최대 파일 크기: {info['max_file_size_mb']}MB")
    
    # 3. 테스트 파일 생성 (간단한 텍스트 파일)
    test_file_path = Path("test_upload.txt")
    test_file_path.write_text("This is a test file for upload functionality.", encoding='utf-8')
    
    # 4. 단일 파일 업로드 테스트
    with open(test_file_path, 'rb') as f:
        files = {"file": ("test_upload.txt", f, "text/plain")}
        data = {"description": "Test file upload"}
        
        upload_response = requests.post(
            f"{API_BASE}/api/files/single",
            files=files,
            data=data,
            headers=headers
        )
    
    if upload_response.status_code == 200:
        result = upload_response.json()
        print(f"파일 업로드 성공: {result['data']['filename']}")
        uploaded_filename = result['data']['filename']
        uploaded_category = result['data']['category']
    else:
        print(f"파일 업로드 실패: {upload_response.status_code} - {upload_response.text}")
        test_file_path.unlink()  # 테스트 파일 삭제
        return
    
    # 5. 파일 목록 조회 테스트
    list_response = requests.get(f"{API_BASE}/api/files/list", headers=headers)
    
    if list_response.status_code == 200:
        file_list = list_response.json()
        print(f"업로드된 파일 수: {file_list['total']}")
        if file_list['files']:
            print(f"최근 업로드 파일: {file_list['files'][0]['filename']}")
    
    # 6. 파일 다운로드 테스트
    download_response = requests.get(
        f"{API_BASE}/api/files/download/{uploaded_category}/{uploaded_filename}",
        headers=headers
    )
    
    if download_response.status_code == 200:
        print("파일 다운로드 성공")
        # 다운로드한 파일 내용 확인
        if download_response.text.strip() == "This is a test file for upload functionality.":
            print("다운로드한 파일 내용이 올바릅니다")
        else:
            print("다운로드한 파일 내용이 일치하지 않습니다")
    else:
        print(f"파일 다운로드 실패: {download_response.status_code}")
    
    # 7. 파일 통계 조회 (관리자 권한)
    stats_response = requests.get(f"{API_BASE}/api/files/stats", headers=headers)
    
    if stats_response.status_code == 200:
        stats = stats_response.json()
        print(f"총 파일 수: {stats['total_files']}")
        print(f"총 크기: {stats['total_size_mb']}MB")
    
    # 정리: 테스트 파일 삭제
    test_file_path.unlink()
    print("파일 업로드 기능 테스트 완료")


if __name__ == "__main__":
    asyncio.run(test_file_upload())