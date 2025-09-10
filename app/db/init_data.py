from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import random
import os

from app.models.user import User, UserRole, UserStatus
from app.models.campaign import Campaign, CampaignStatus
from app.models.purchase_request import PurchaseRequest, RequestStatus
from app.core.security import get_password_hash


async def create_superuser(db: AsyncSession):
    """슈퍼 어드민 계정 생성"""
    
    # 기존 슈퍼 어드민 확인 (여러 명 있을 수 있으므로 첫 번째만 확인)
    query = select(User).where(User.role == UserRole.SUPER_ADMIN).limit(1)
    result = await db.execute(query)
    existing_superuser = result.scalar_one_or_none()
    
    if existing_superuser:
        print("슈퍼 어드민 계정이 이미 존재합니다.")
        return existing_superuser
    
    # 환경변수에서 슈퍼 어드민 정보 가져오기 (기본값 포함)
    admin_email = os.getenv("SUPERUSER_EMAIL", "admin@brandflow.com")
    admin_password = os.getenv("SUPERUSER_PASSWORD", "BrandFlow2024!Admin")
    admin_name = os.getenv("SUPERUSER_NAME", "시스템 관리자")
    
    # 슈퍼 어드민 생성
    superuser = User(
        name=admin_name,
        email=admin_email,
        hashed_password=get_password_hash(admin_password),
        role=UserRole.SUPER_ADMIN,
        company="BrandFlow Korea",
        contact=None,
        incentive_rate=0.0,
        status=UserStatus.ACTIVE,
        is_active=True
    )
    
    db.add(superuser)
    await db.flush()
    await db.refresh(superuser)
    
    print("슈퍼 어드민 계정이 생성되었습니다.")
    print(f"   이메일: {superuser.email}")
    print(f"   이름: {superuser.name}")
    print("   비밀번호는 환경변수 SUPERUSER_PASSWORD로 설정됨")
    
    return superuser


async def create_test_users(db: AsyncSession):
    """테스트 사용자들 생성"""
    
    # 기존 테스트 유저 확인
    test_user_query = select(User).where(User.email == "test@example.com")
    existing_test_user = await db.scalar(test_user_query)
    
    if existing_test_user:
        print("테스트 유저가 이미 존재합니다.")
        return [existing_test_user]
    
    # 다양한 역할의 테스트 유저 생성
    test_users = [
        {
            "name": "김매니저",
            "email": "manager@test.com",
            "role": UserRole.AGENCY_ADMIN,
            "company": "브랜드플로우코리아",
            "contact": "02-1234-5678"
        },
        {
            "name": "박대리",
            "email": "staff@test.com", 
            "role": UserRole.STAFF,
            "company": "브랜드플로우코리아",
            "contact": "02-1234-5679"
        },
        {
            "name": "이클라이언트",
            "email": "client@test.com",
            "role": UserRole.CLIENT,
            "company": "테스트클라이언트",
            "contact": "02-9999-0000"
        }
    ]
    
    created_users = []
    
    for user_data in test_users:
        user = User(
            name=user_data["name"],
            email=user_data["email"],
            hashed_password=get_password_hash("TestPassword123!"),
            role=user_data["role"],
            company=user_data["company"],
            contact=user_data["contact"],
            incentive_rate=5.0,
            status=UserStatus.ACTIVE,
            is_active=True
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        created_users.append(user)
        print(f"   테스트 유저 생성: {user.name} ({user.email})")
    
    return created_users


async def create_test_campaigns(db: AsyncSession, users: list):
    """테스트 캠페인들 생성"""
    
    # 기존 캠페인 확인
    campaign_count = await db.scalar(select(Campaign.id).limit(1))
    if campaign_count:
        print("캠페인 데이터가 이미 존재합니다.")
        return []
    
    # 캠페인 생성할 매니저/슈퍼어드민 찾기
    creator = None
    for user in users:
        if user.role in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
            creator = user
            break
    
    if not creator:
        print("캠페인 생성할 권한 있는 사용자가 없습니다.")
        return []
    
    # 테스트 캠페인 데이터
    test_campaigns = [
        {
            "name": "2024 브랜드 론칭 캠페인",
            "description": "새로운 브랜드의 성공적인 시장 진입을 위한 통합 마케팅 캠페인",
            "client_company": "테스트클라이언트",
            "budget": 5000000.0,
            "status": CampaignStatus.ACTIVE,
            "start_offset": -30,  # 30일 전 시작
            "end_offset": 30      # 30일 후 종료
        },
        {
            "name": "여름 시즌 프로모션",
            "description": "여름 시즌을 겨냥한 제품 프로모션 및 이벤트 캠페인",
            "client_company": "써머브랜드",
            "budget": 3000000.0,
            "status": CampaignStatus.COMPLETED,
            "start_offset": -60,  # 60일 전 시작
            "end_offset": -10     # 10일 전 종료
        },
        {
            "name": "Q4 연말 마케팅 캠페인",
            "description": "연말 성수기를 대비한 대규모 통합 마케팅 캠페인",
            "client_company": "연말브랜드",
            "budget": 8000000.0,
            "status": CampaignStatus.DRAFT,
            "start_offset": 15,   # 15일 후 시작
            "end_offset": 90      # 90일 후 종료
        }
    ]
    
    created_campaigns = []
    
    for campaign_data in test_campaigns:
        start_date = datetime.now() + timedelta(days=campaign_data["start_offset"])
        end_date = datetime.now() + timedelta(days=campaign_data["end_offset"])
        
        campaign = Campaign(
            name=campaign_data["name"],
            client_company=campaign_data["client_company"],
            budget=campaign_data["budget"],
            start_date=start_date,
            end_date=end_date,
            status=campaign_data["status"],
            creator_id=creator.id
        )
        
        db.add(campaign)
        await db.flush()
        await db.refresh(campaign)
        created_campaigns.append(campaign)
        print(f"   테스트 캠페인 생성: {campaign.name} ({campaign.status})")
    
    return created_campaigns


async def create_test_purchase_requests(db: AsyncSession, users: list, campaigns: list):
    """테스트 구매요청들 생성"""
    
    # 기존 구매요청 확인
    request_count = await db.scalar(select(PurchaseRequest.id).limit(1))
    if request_count:
        print("구매요청 데이터가 이미 존재합니다.")
        return []
    
    if not campaigns:
        print("구매요청을 연결할 캠페인이 없습니다.")
        return []
    
    # 구매요청 생성할 사용자들 (모든 활성 사용자)
    active_users = [u for u in users if u.is_active]
    if not active_users:
        print("구매요청을 생성할 활성 사용자가 없습니다.")
        return []
    
    # 테스트 구매요청 데이터
    test_requests = [
        {
            "title": "프린팅 서비스",
            "description": "브로셔, 포스터, 명함 제작을 위한 프린팅 서비스",
            "amount": 500000.0,
            "quantity": 1000,
            "vendor": "프린팅플러스",
            "status": RequestStatus.APPROVED
        },
        {
            "title": "광고 대행사 계약",
            "description": "온라인 광고 집행 및 관리를 위한 대행사 계약",
            "amount": 2000000.0,
            "quantity": 1,
            "vendor": "디지털광고대행",
            "status": RequestStatus.COMPLETED
        },
        {
            "title": "이벤트 부스 임대",
            "description": "전시회 참가를 위한 부스 임대 및 세팅",
            "amount": 800000.0,
            "quantity": 2,
            "vendor": "이벤트프로",
            "status": RequestStatus.PENDING
        },
        {
            "title": "촬영 스튜디오 렌탈",
            "description": "제품 촬영을 위한 스튜디오 임대",
            "amount": 300000.0,
            "quantity": 3,
            "vendor": "스튜디오렌탈",
            "status": RequestStatus.REJECTED
        },
        {
            "title": "소셜미디어 관리 도구",
            "description": "SNS 콘텐츠 관리를 위한 도구 구독",
            "amount": 150000.0,
            "quantity": 12,
            "vendor": "소셜툴즈",
            "status": RequestStatus.APPROVED
        }
    ]
    
    created_requests = []
    
    for i, request_data in enumerate(test_requests):
        # 사용자와 캠페인 랜덤 배정
        requester = random.choice(active_users)
        campaign = random.choice(campaigns) if campaigns else None
        
        request = PurchaseRequest(
            title=request_data["title"],
            description=request_data["description"],
            amount=request_data["amount"],
            quantity=request_data["quantity"],
            vendor=request_data["vendor"],
            status=request_data["status"],
            requester_id=requester.id,
            campaign_id=campaign.id if campaign else None
        )
        
        db.add(request)
        await db.flush()
        await db.refresh(request)
        created_requests.append(request)
        print(f"   테스트 구매요청 생성: {request.title} ({request.status}) - {requester.name}")
    
    return created_requests


async def init_database_data(db: AsyncSession):
    """데이터베이스 초기 데이터 생성 - 환경별 전략"""
    # 환경 확인
    is_production = os.getenv('RAILWAY_ENVIRONMENT_NAME') == 'production' or os.getenv('ENV') == 'production'
    is_dev = os.getenv('ENV') == 'development' or not os.getenv('PORT')  # 로컬은 개발환경
    
    if is_production:
        print("프로덕션 환경 - 슈퍼 어드민만 생성...")
    else:
        print("개발/테스트 환경 - 완전한 테스트 데이터 생성...")
    
    try:
        # 1. 슈퍼 어드민 계정 생성 (모든 환경에서 필수)
        superuser = await create_superuser(db)
        
        if is_production:
            # 프로덕션: 슈퍼 어드민만 생성
            await db.commit()
            print(f"\n=== 프로덕션 초기 데이터 생성 완료 ===")
            print(f"슈퍼 어드민 계정만 생성됨:")
            print(f"  이메일: {superuser.email}")
            print(f"  이름: {superuser.name}")
            print(f"  회사: {superuser.company}")
            print(f"  기본 비밀번호: BrandFlow2024!Admin")
            print(f"  (환경변수 SUPERUSER_PASSWORD로 변경 가능)")
            print(f"=============================")
        else:
            # 개발/테스트: 완전한 테스트 데이터 생성
            # 2. 테스트 사용자들 생성
            test_users = await create_test_users(db)
            all_users = [superuser] + test_users
            
            # 3. 테스트 캠페인들 생성
            test_campaigns = await create_test_campaigns(db, all_users)
            
            # 4. 테스트 구매요청들 생성
            test_requests = await create_test_purchase_requests(db, all_users, test_campaigns)
            
            await db.commit()
            print(f"\n=== 개발환경 초기 데이터 생성 완료 ===")
            print(f"사용자 수: {len(all_users)}명")
            print(f"캠페인 수: {len(test_campaigns)}개")
            print(f"구매요청 수: {len(test_requests)}개")
            print(f"")
            print(f"슈퍼 어드민 계정:")
            print(f"  이메일: {superuser.email}")
            print(f"  이름: {superuser.name}")
            print(f"  회사: {superuser.company}")
            print(f"  기본 비밀번호: BrandFlow2024!Admin")
            print(f"=============================")
        
    except Exception as e:
        print(f"초기 데이터 생성 중 오류 발생: {str(e)}")
        await db.rollback()
        raise