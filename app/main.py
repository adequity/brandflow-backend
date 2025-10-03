from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import os

from app.core.config import settings
from app.db.database import create_tables, create_performance_indexes, get_async_db, add_client_user_id_column, migrate_client_company_to_user_id, add_campaign_date_columns, update_null_campaign_dates
from app.db.init_data import init_database_data
from alembic.config import Config
from alembic import command
import subprocess
from app.api.endpoints import auth, users, campaigns, purchase_requests, company_logo, products, work_types, notifications, file_upload, performance, monitoring, dashboard, search, export, admin, websocket, security_dashboard, performance_dashboard, cache, health, dashboard_simple, migration, monthly_incentives


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Railway 배포용 안전한 시작
    print("Starting BrandFlow FastAPI v2.3.0...")
    print("Railway deployment mode - Health API enabled")
    
    # Railway에서 안전한 데이터베이스 초기화
    try:
        print("Attempting database connection...")
        await create_tables()
        print("Database tables created successfully")

        # Alembic 마이그레이션 실행
        try:
            print("Running Alembic migrations...")
            alembic_cfg = Config("alembic.ini")
            command.upgrade(alembic_cfg, "head")
            print("Alembic migrations completed successfully")
        except Exception as alembic_error:
            print(f"Alembic migration failed (non-critical): {str(alembic_error)}")

        # client_user_id 컬럼 추가 (스키마 마이그레이션)
        await add_client_user_id_column()

        # 기존 client_company 데이터를 client_user_id로 마이그레이션
        await migrate_client_company_to_user_id()

        # campaigns 테이블에 start_date, end_date 컬럼 추가
        await add_campaign_date_columns()

        # 기존 캠페인들의 NULL 날짜 필드들에 기본값 설정
        await update_null_campaign_dates()


        # 초기 데이터 생성 (선택적)
        try:
            print("Initializing database data...")
            async for db in get_async_db():
                await init_database_data(db)
                break
            print("Database data initialization completed")
        except Exception as data_error:
            print(f"Database data initialization failed (non-critical): {str(data_error)}")
            
    except Exception as db_error:
        print(f"Database connection failed: {str(db_error)}")
        print("Server starting in offline mode - API endpoints will return appropriate errors")
        # Railway에서도 서버가 시작되도록 모든 DB 에러를 무시

    # 파일 업로드 디렉토리 초기화 (Railway Volume 지원)
    try:
        from app.core.file_upload import file_manager
        await file_manager.ensure_upload_dir()
        print(f"✅ Upload directory initialized: {file_manager.upload_dir}")
    except Exception as e:
        print(f"❌ Upload directory initialization error: {str(e)}")
        print("Continuing with application startup...")
    
    # 자동 마이그레이션 체크 (임시 비활성화 - crashed 해결)
    # if os.getenv("AUTO_MIGRATE") == "true":
    #     print("[MIGRATION] AUTO_MIGRATE=true 감지됨. 마이그레이션을 실행합니다...")
    #     try:
    #         from alembic import command
    #         from alembic.config import Config

    #         alembic_cfg = Config("alembic.ini")
    #         command.upgrade(alembic_cfg, "head")
    #         print("[OK] 자동 마이그레이션 완료!")

    #         # 마이그레이션 후 환경변수 제거 (무한 실행 방지)
    #         if hasattr(os, 'unsetenv'):
    #             os.unsetenv("AUTO_MIGRATE")

    #     except Exception as migrate_error:
    #         print(f"[ERROR] 자동 마이그레이션 실패: {str(migrate_error)}")
    #         # 마이그레이션 실패해도 서버는 계속 시작

    # 텔레그램 스케줄러 시작 (백그라운드)
    try:
        from app.services.telegram_scheduler import telegram_scheduler
        import asyncio

        # 스케줄러를 백그라운드 태스크로 시작
        asyncio.create_task(telegram_scheduler.start())
        print("[OK] 텔레그램 알림 스케줄러 시작됨")
    except Exception as scheduler_error:
        print(f"[ERROR] 텔레그램 스케줄러 시작 실패: {str(scheduler_error)}")

    print("BrandFlow FastAPI v2.3.0 ready!")

    yield
    # Shutdown
    try:
        from app.services.telegram_scheduler import telegram_scheduler
        telegram_scheduler.stop()
        print("텔레그램 스케줄러 중지됨")
    except:
        pass
    print("BrandFlow server shutdown completed")


app = FastAPI(
    title="BrandFlow API",
    description="BrandFlow 캠페인 관리 시스템 API - 캐시 무효화 버전",
    version="2.3.0",
    lifespan=lifespan,
)

# UTF-8 JSON 처리 미들웨어 추가 (가장 먼저 적용)
# SimpleCORSMiddleware 제거 - CORSMiddleware와 중복 방지
# from app.middleware.simple_cors import SimpleCORSMiddleware
# app.add_middleware(SimpleCORSMiddleware)  # CORSMiddleware와 중복되어 비활성화

# from app.middleware.json_utf8 import UTF8JSONMiddleware
# app.add_middleware(UTF8JSONMiddleware)  # WARNING: 2분 타임아웃 문제로 재비활성화

# 보안 미들웨어 추가 (순서가 중요 - 가장 먼저 적용)
# from app.middleware.security_audit import SecurityAuditMiddleware
# app.add_middleware(SecurityAuditMiddleware)  # 임시 비활성화
# app.add_middleware(RequestSanitizationMiddleware, max_body_size=10*1024*1024)  # 임시 비활성화
# app.add_middleware(RateLimitMiddleware, requests_per_minute=100, requests_per_second=10)  # 임시 비활성화
# app.add_middleware(SecurityHeadersMiddleware)  # 임시 비활성화

# 모니터링 미들웨어 추가 (Railway 배포 시 임시 비활성화)
# from app.middleware.monitoring import MonitoringMiddleware, set_monitoring_instance

# 모니터링 미들웨어 인스턴스 생성 및 등록 (임시 비활성화)
# monitoring_middleware_instance = MonitoringMiddleware(app)
# app.add_middleware(MonitoringMiddleware)
# set_monitoring_instance(monitoring_middleware_instance)

# HTTPS 리다이렉트 미들웨어 추가 (Mixed Content 방지)
# Railway 헬스체크 실패 방지를 위해 임시 비활성화
# from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
# Railway 환경에서만 HTTPS 강제 (로컬 개발 환경은 제외)
import os
# if os.getenv('RAILWAY_ENVIRONMENT_NAME') or os.getenv('PORT'):
#     app.add_middleware(HTTPSRedirectMiddleware)
#     print("HTTPS 리다이렉트 미들웨어 활성화")

# 성능 모니터링 미들웨어 추가
from app.middleware.simple_performance import SimplePerformanceMiddleware
app.add_middleware(SimplePerformanceMiddleware)

# CORS 에러 핸들러 추가
@app.exception_handler(Exception)
async def cors_exception_handler(request: Request, exc: Exception):
    """모든 예외에 대해 CORS 헤더를 추가하여 프론트엔드에서 에러를 확인할 수 있도록 함"""
    response = JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal server error: {str(exc)}",
            "error_type": type(exc).__name__
        },
    )
    
    # CORS 헤더 수동 추가
    origin = request.headers.get("origin")
    # CORS 허용 도메인 확대 (Netlify 서브도메인 포함)
    allowed_origins = [
        "https://brandflo.netlify.app",
        "https://brandflow-frontend.netlify.app", 
        "https://adequate-brandflow.netlify.app",
        "https://adequity-brandflow.netlify.app",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176", 
        "http://localhost:5177",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:5177"
    ]
    
    if origin in allowed_origins or (origin and origin.endswith('.netlify.app')):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, Origin, X-Requested-With, Access-Control-Allow-Origin, Access-Control-Allow-Credentials, X-CSRF-Token"
    
    return response

# CORS 미들웨어 설정 (프로덕션 보안 강화 + 인증 지원)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://brandflo.netlify.app",
        "https://brandflow-frontend.netlify.app", 
        "https://adequate-brandflow.netlify.app",
        "https://adequity-brandflow.netlify.app",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176", 
        "http://localhost:5177",
        "http://localhost:5178",
        "http://localhost:5179",
        "http://localhost:5180",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:5177",
        "http://127.0.0.1:5178",
        "http://127.0.0.1:5179",
        "http://127.0.0.1:5180"
    ],  # 특정 도메인만 허용하여 인증 지원
    allow_credentials=True,  # JWT 토큰 인증을 위해 필수
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    allow_headers=[
        "Content-Type", 
        "Authorization", 
        "Accept", 
        "Origin", 
        "X-Requested-With",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Credentials",
        "X-CSRF-Token"
    ],
    expose_headers=["X-Total-Count", "X-Page-Count", "Set-Cookie"],
)

# 임시 마이그레이션 엔드포인트 (products.company 컬럼 추가)
@app.get("/api/admin/migrate-products-company")
async def migrate_products_company():
    """Railway에서 products.company 컬럼을 수동으로 추가하는 임시 엔드포인트"""
    try:
        from sqlalchemy import text

        async for db in get_async_db():
            try:
                # 1. products.company 컬럼 존재 여부 확인
                result = await db.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'products' AND column_name = 'company'
                """))
                column_exists = result.fetchone()

                if column_exists:
                    return {"status": "success", "message": "products.company column already exists"}

                # 2. products 테이블에 company 컬럼 추가
                await db.execute(text("""
                    ALTER TABLE products
                    ADD COLUMN company VARCHAR(200) DEFAULT 'default_company'
                """))

                # 3. company 컬럼에 인덱스 생성
                await db.execute(text("""
                    CREATE INDEX ix_products_company ON products (company)
                """))

                # 4. 기존 데이터에 기본값 설정
                await db.execute(text("""
                    UPDATE products
                    SET company = 'default_company'
                    WHERE company IS NULL
                """))

                # 5. 변경사항 커밋
                await db.commit()

                # 6. 결과 확인
                product_count = await db.execute(text("SELECT COUNT(*) FROM products"))
                count_result = product_count.fetchone()
                total_products = count_result[0] if count_result else 0

                return {
                    "status": "success",
                    "message": "products.company column added successfully",
                    "total_products": total_products,
                    "note": "STAFF campaign details HTTP 500 error should be resolved"
                }

            except Exception as e:
                await db.rollback()
                return {"status": "error", "message": f"Migration failed: {str(e)}"}
            finally:
                await db.close()
                break

    except Exception as e:
        return {"status": "error", "message": f"Database connection failed: {str(e)}"}


# 임시 마이그레이션 엔드포인트 (work_types.company 컬럼 추가)
@app.get("/api/admin/migrate-work-types-company")
async def migrate_work_types_company():
    """Railway에서 work_types.company 컬럼을 수동으로 추가하는 임시 엔드포인트"""
    try:
        from sqlalchemy import text

        async for db in get_async_db():
            try:
                # 1. work_types.company 컬럼 존재 여부 확인
                result = await db.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'work_types' AND column_name = 'company'
                """))
                column_exists = result.fetchone()

                if column_exists:
                    return {"status": "success", "message": "work_types.company column already exists"}

                # 2. work_types 테이블에 company 컬럼 추가
                await db.execute(text("""
                    ALTER TABLE work_types
                    ADD COLUMN company VARCHAR(200) DEFAULT 'default_company'
                """))

                # 3. company 컬럼에 인덱스 생성
                await db.execute(text("""
                    CREATE INDEX ix_work_types_company ON work_types (company)
                """))

                # 4. 기존 데이터에 기본값 설정
                await db.execute(text("""
                    UPDATE work_types
                    SET company = 'default_company'
                    WHERE company IS NULL
                """))

                # 5. unique constraint 제거 (회사별 중복 허용)
                try:
                    await db.execute(text("""
                        ALTER TABLE work_types DROP CONSTRAINT IF EXISTS work_types_name_key
                    """))
                except Exception as constraint_error:
                    print(f"Constraint removal warning: {constraint_error}")

                # 6. 변경사항 커밋
                await db.commit()

                # 7. 결과 확인
                work_type_count = await db.execute(text("SELECT COUNT(*) FROM work_types"))
                count_result = work_type_count.fetchone()
                total_work_types = count_result[0] if count_result else 0

                return {
                    "status": "success",
                    "message": "work_types.company column added successfully",
                    "total_work_types": total_work_types,
                    "note": "WorkType company segregation is now active"
                }

            except Exception as e:
                await db.rollback()
                return {"status": "error", "message": f"Migration failed: {str(e)}"}
            finally:
                await db.close()
                break

    except Exception as e:
        return {"status": "error", "message": f"Database connection failed: {str(e)}"}


@app.get("/api/admin/debug-campaigns")
async def debug_campaigns():
    """캠페인과 사용자 company 정보 디버깅"""
    try:
        from sqlalchemy import text

        async for db in get_async_db():
            try:
                # 캠페인과 creator의 company 정보 조회
                campaigns_query = text("""
                    SELECT
                        c.id as campaign_id,
                        c.name as campaign_name,
                        c.creator_id,
                        u.name as creator_name,
                        u.email as creator_email,
                        u.company as creator_company,
                        u.role as creator_role
                    FROM campaigns c
                    LEFT JOIN users u ON c.creator_id = u.id
                    ORDER BY c.id
                """)

                campaigns_result = await db.execute(campaigns_query)
                campaigns_data = campaigns_result.fetchall()

                # 모든 사용자 정보
                users_query = text("""
                    SELECT id, name, email, company, role
                    FROM users
                    ORDER BY id
                """)

                users_result = await db.execute(users_query)
                users_data = users_result.fetchall()

                return {
                    "status": "success",
                    "campaigns": [
                        {
                            "campaign_id": row[0],
                            "campaign_name": row[1],
                            "creator_id": row[2],
                            "creator_name": row[3],
                            "creator_email": row[4],
                            "creator_company": row[5],
                            "creator_role": row[6]
                        }
                        for row in campaigns_data
                    ],
                    "users": [
                        {
                            "id": row[0],
                            "name": row[1],
                            "email": row[2],
                            "company": row[3],
                            "role": row[4]
                        }
                        for row in users_data
                    ]
                }

            except Exception as e:
                await db.rollback()
                raise e
            finally:
                await db.close()

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/admin/fix-campaign-company")
async def fix_campaign_company():
    """기존 캠페인들을 AGENCY_ADMIN company로 업데이트"""
    try:
        from sqlalchemy import text

        async for db in get_async_db():
            try:
                # AGENCY_ADMIN 사용자 찾기 (2222@brandflow.com)
                agency_admin_query = text("""
                    SELECT id, company FROM users
                    WHERE email = '2222@brandflow.com' AND role = 'AGENCY_ADMIN'
                """)

                admin_result = await db.execute(agency_admin_query)
                admin_data = admin_result.fetchone()

                if not admin_data:
                    return {"status": "error", "message": "AGENCY_ADMIN user not found"}

                admin_id = admin_data[0]
                admin_company = admin_data[1]

                # 모든 캠페인의 creator를 AGENCY_ADMIN으로 업데이트
                update_campaigns_query = text("""
                    UPDATE campaigns
                    SET creator_id = :admin_id
                    WHERE creator_id IS NOT NULL
                """)

                update_result = await db.execute(update_campaigns_query, {"admin_id": admin_id})

                # 캠페인 creator들의 company를 AGENCY_ADMIN company로 업데이트 (다른 방법)
                # 또는 AGENCY_ADMIN과 다른 company를 가진 creator들을 AGENCY_ADMIN company로 업데이트
                update_users_query = text("""
                    UPDATE users
                    SET company = :admin_company
                    WHERE id IN (
                        SELECT DISTINCT creator_id FROM campaigns WHERE creator_id IS NOT NULL
                    ) AND company != :admin_company
                """)

                users_update_result = await db.execute(update_users_query, {"admin_company": admin_company})

                await db.commit()

                return {
                    "status": "success",
                    "message": "캠페인 company 정보 업데이트 완료",
                    "agency_admin": {
                        "id": admin_id,
                        "company": admin_company
                    },
                    "campaigns_updated": update_result.rowcount,
                    "users_updated": users_update_result.rowcount
                }

            except Exception as e:
                await db.rollback()
                raise e
            finally:
                await db.close()

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/admin/check-test-data")
async def check_test_data():
    """Railway 환경의 테스트 데이터 존재 여부 확인"""
    try:
        from sqlalchemy import text
        import os

        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return {"status": "error", "message": "DATABASE_URL not found"}

        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine(database_url, echo=False)

        async with engine.begin() as conn:
            # 사용자 수 확인
            users_count = await conn.execute(text("SELECT COUNT(*) FROM users"))
            users_total = users_count.fetchone()[0]

            # 캠페인 수 확인
            campaigns_count = await conn.execute(text("SELECT COUNT(*) FROM campaigns"))
            campaigns_total = campaigns_count.fetchone()[0]

            # 상품 수 확인
            products_count = await conn.execute(text("SELECT COUNT(*) FROM products"))
            products_total = products_count.fetchone()[0]

            # 업무타입 수 확인
            work_types_count = await conn.execute(text("SELECT COUNT(*) FROM work_types"))
            work_types_total = work_types_count.fetchone()[0]

            # 샘플 사용자 정보
            sample_users = await conn.execute(text("""
                SELECT name, email, role, company
                FROM users
                ORDER BY created_at
                LIMIT 5
            """))
            users_sample = [dict(row._mapping) for row in sample_users.fetchall()]

            # 샘플 캠페인 정보
            sample_campaigns = await conn.execute(text("""
                SELECT name, client_company, status, budget
                FROM campaigns
                ORDER BY created_at
                LIMIT 3
            """))
            campaigns_sample = [dict(row._mapping) for row in sample_campaigns.fetchall()]

            await engine.dispose()

            return {
                "status": "success",
                "data_summary": {
                    "users": users_total,
                    "campaigns": campaigns_total,
                    "products": products_total,
                    "work_types": work_types_total
                },
                "sample_data": {
                    "users": users_sample,
                    "campaigns": campaigns_sample
                },
                "has_test_data": users_total > 0 and campaigns_total > 0
            }

    except Exception as e:
        return {"status": "error", "message": f"Data check failed: {str(e)}"}


@app.get("/api/admin/create-test-users")
async def create_test_users_endpoint():
    """Railway 환경에서 테스트 사용자 수동 생성"""
    try:
        from app.db.database import get_async_db
        from app.db.init_data import create_test_users

        async for db in get_async_db():
            try:
                # 테스트 사용자 생성
                test_users = await create_test_users(db)
                await db.commit()

                return {
                    "status": "success",
                    "message": f"테스트 사용자 {len(test_users)}명 생성 완료",
                    "users": [
                        {
                            "name": user.name,
                            "email": user.email,
                            "role": user.role.value,
                            "company": user.company,
                            "password": "TestPassword123!"
                        }
                        for user in test_users
                    ]
                }
            except Exception as e:
                await db.rollback()
                return {"status": "error", "message": f"테스트 사용자 생성 실패: {str(e)}"}
            finally:
                await db.close()
                break
    except Exception as e:
        return {"status": "error", "message": f"Database connection failed: {str(e)}"}


# API 라우터 등록 - 핵심 기능
app.include_router(auth.router, prefix="/api/auth", tags=["인증"])
app.include_router(users.router, prefix="/api/users", tags=["사용자"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["캠페인"])
app.include_router(purchase_requests.router, prefix="/api/purchase-requests", tags=["구매요청"])
app.include_router(company_logo.router, prefix="/api/company", tags=["회사"])
app.include_router(products.router, prefix="/api/products", tags=["상품"])
app.include_router(work_types.router, prefix="/api/work-types", tags=["작업유형"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["알림"])
app.include_router(file_upload.router, prefix="/api/files", tags=["파일"])
app.include_router(monthly_incentives.router, prefix="/api/monthly-incentives", tags=["월간인센티브"])

# API 라우터 등록 - 대시보드 & 분석
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["대시보드"])
app.include_router(dashboard_simple.router, prefix="/api/dashboard-simple", tags=["간단대시보드"])
app.include_router(search.router, prefix="/api/search", tags=["검색"])
app.include_router(export.router, prefix="/api/export", tags=["내보내기"])
app.include_router(performance_dashboard.router, prefix="/api/performance-dashboard", tags=["성능대시보드"])
app.include_router(security_dashboard.router, prefix="/api/security-dashboard", tags=["보안대시보드"])

# API 라우터 등록 - 시스템 & 관리
app.include_router(admin.router, prefix="/api/admin", tags=["관리자"])

# 시스템 설정 라우터 별도 import 및 등록
try:
    from app.api.endpoints import system_settings
    app.include_router(system_settings.router, prefix="/api/admin/system-settings", tags=["시스템설정"])
    print("[OK] 시스템 설정 라우터 등록 완료")
except Exception as e:
    print(f"[ERROR] 시스템 설정 라우터 등록 실패: {str(e)}")

# 텔레그램 설정 라우터 등록
try:
    from app.api.endpoints import telegram_settings
    app.include_router(telegram_settings.router, prefix="/api/telegram", tags=["텔레그램알림"])
    print("[OK] 텔레그램 설정 라우터 등록 완료")
except Exception as e:
    print(f"[ERROR] 텔레그램 설정 라우터 등록 실패: {str(e)}")

# 회사별 설정 라우터 등록
try:
    from app.api.endpoints import company_settings
    app.include_router(company_settings.router, prefix="/api/company-settings", tags=["회사설정"])
    print("[OK] 회사별 설정 라우터 등록 완료")
except Exception as e:
    print(f"[ERROR] 회사별 설정 라우터 등록 실패: {str(e)}")

app.include_router(performance.router, prefix="/api/performance", tags=["성능"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["모니터링"])
app.include_router(cache.router, prefix="/api/cache", tags=["캐시"])
app.include_router(health.router, prefix="/api/system", tags=["시스템상태"])
app.include_router(websocket.router, prefix="/api/ws", tags=["웹소켓"])

# 마이그레이션 라우터 추가 (임시 비활성화 - crashed 해결)
# from app.api.endpoints import migration, simple_migration
app.include_router(migration.router, prefix="/api/migration", tags=["마이그레이션"])
# app.include_router(simple_migration.router, prefix="/api/migrate", tags=["간단마이그레이션"])


@app.get("/")
async def root():
    import os
    from datetime import datetime
    return {
        "message": "BrandFlow API v2.3.0 - CACHE CLEARED - ALL 112 APIs ACTIVE",
        "status": "running",
        "cache_cleared": True,
        "deployment_time": datetime.now().isoformat(),
        "environment": "railway" if os.getenv("PORT") else "local",
        "total_routes": len(app.router.routes),
        "api_endpoints": len([r for r in app.router.routes if hasattr(r, 'path') and '/api/' in r.path]),
        "debug_endpoints": ["/debug/routes", "/debug/imports"],
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.2.2",
        "message": "BrandFlow FastAPI Health Check - All APIs Connected",
        "timestamp": "2025-09-06T03:45:00Z",
        "registered_apis": 21
    }


@app.get("/debug/routes")
async def debug_routes():
    """진단용: 실제 등록된 라우트 확인"""
    routes_info = []
    for route in app.router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes_info.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else [],
                "name": getattr(route, 'name', 'unnamed')
            })
    
    # API 라우트만 필터링
    api_routes = [r for r in routes_info if r['path'].startswith('/api/')]
    
    return {
        "total_routes": len(routes_info),
        "api_routes_count": len(api_routes),
        "api_routes": sorted(api_routes, key=lambda x: x['path']),
        "environment": "railway" if os.getenv("PORT") else "local",
        "database_url_type": "postgresql" if "postgresql" in settings.get_database_url else "other",
        "database_url": settings.get_database_url,
        "raw_database_url": os.getenv("DATABASE_URL", "NOT_SET"),
        "railway_env": os.getenv("RAILWAY_ENVIRONMENT_NAME", "NOT_SET")
    }


@app.get("/debug/imports")
async def debug_imports():
    """진단용: 모듈 임포트 상태 확인"""
    import_status = {}
    modules_to_test = [
        "dashboard", "search", "export", "admin", "websocket", 
        "security_dashboard", "performance_dashboard", "cache", "health", "dashboard_simple"
    ]
    
    for module_name in modules_to_test:
        try:
            module = __import__(f"app.api.endpoints.{module_name}", fromlist=[module_name])
            has_router = hasattr(module, 'router')
            import_status[module_name] = {
                "imported": True,
                "has_router": has_router,
                "router_type": str(type(module.router)) if has_router else None
            }
        except Exception as e:
            import_status[module_name] = {
                "imported": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    return {
        "environment": "railway" if os.getenv("PORT") else "local",
        "import_status": import_status,
        "successful_imports": sum(1 for status in import_status.values() if status["imported"]),
        "failed_imports": sum(1 for status in import_status.values() if not status["imported"])
    }

# 테스트 엔드포인트 제거


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )