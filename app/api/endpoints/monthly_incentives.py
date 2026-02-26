from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, extract, desc, func, select
from sqlalchemy.orm import selectinload
from typing import List, Optional
import logging
from datetime import datetime

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole
from app.models.monthly_incentive import MonthlyIncentive, IncentiveStatus
from app.models.campaign import Campaign, CampaignStatus
from app.models.post import Post
from app.schemas.monthly_incentive import (
    MonthlyIncentiveResponse,
    MonthlyIncentiveUpdate,
    IncentiveCalculationRequest,
    IncentiveCalculationResponse,
    IncentiveCalculationResult,
    IncentiveStatsResponse,
    IncentiveListQuery
)

# 로거 설정
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
async def health_check():
    """월간 인센티브 시스템 헬스 체크"""
    return {
        "status": "healthy",
        "message": "월간 인센티브 시스템이 정상 작동 중입니다",
        "timestamp": datetime.now().isoformat()
    }

@router.post("/calculate", response_model=IncentiveCalculationResponse)
async def calculate_monthly_incentives(
    request: IncentiveCalculationRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """월간 인센티브 계산"""

    # 권한 확인
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다")

    logger.info(f"월간 인센티브 계산 시작: {request.year}년 {request.month}월")

    results = []
    summary = {"created": 0, "updated": 0, "skipped": 0, "error": 0}

    try:
        # 대상 사용자 조회 (권한별 필터링)
        user_query = select(User).where(
            User.role.in_([UserRole.STAFF, UserRole.AGENCY_ADMIN])
        )

        # 회사별 필터링 (AGENCY_ADMIN은 자신 회사만)
        if current_user.role == UserRole.AGENCY_ADMIN:
            user_query = user_query.where(User.company == current_user.company)
        elif request.company:
            user_query = user_query.where(User.company == request.company)

        users_result = await db.execute(user_query)
        target_users = users_result.scalars().all()

        logger.info(f"대상 사용자 {len(target_users)}명 조회 완료")

        for user in target_users:
            try:
                # 기존 인센티브 데이터 확인
                existing_query = select(MonthlyIncentive).where(
                    and_(
                        MonthlyIncentive.user_id == user.id,
                        MonthlyIncentive.year == request.year,
                        MonthlyIncentive.month == request.month
                    )
                )
                existing_result = await db.execute(existing_query)
                existing_incentive = existing_result.scalar_one_or_none()

                # 재계산 옵션이 False이고 기존 데이터가 있으면 건너뛰기
                if existing_incentive and not request.recalculate:
                    results.append(IncentiveCalculationResult(
                        user_id=user.id,
                        user_name=user.name,
                        company=user.company or "미설정",
                        status="skipped",
                        message="이미 계산된 데이터 존재",
                        incentive_amount=existing_incentive.final_incentive_amount
                    ))
                    summary["skipped"] += 1
                    continue

                print(f"[MONTHLY-INCENTIVE] 사용자 {user.name} (ID: {user.id}) 캠페인 조회 - 요청 년/월: {request.year}/{request.month}")

                # 모든 캠페인 먼저 확인 (디버깅용)
                all_campaigns_query = select(Campaign).where(Campaign.staff_id == user.id)
                all_campaigns_result = await db.execute(all_campaigns_query)
                all_campaigns = all_campaigns_result.scalars().all()

                print(f"[MONTHLY-INCENTIVE] 전체 캠페인 ({len(all_campaigns)}개):")
                for campaign in all_campaigns:
                    campaign_year = campaign.start_date.year if campaign.start_date else None
                    campaign_month = campaign.start_date.month if campaign.start_date else None
                    extract_year = campaign.start_date.year if campaign.start_date else None
                    extract_month = campaign.start_date.month if campaign.start_date else None
                    matches_filter = (extract_year == request.year and extract_month == request.month)
                    print(f"  - 캠페인 {campaign.id}: {campaign.name}")
                    print(f"    시작일: {campaign.start_date} (연도: {campaign_year}, 월: {campaign_month})")
                    print(f"    요청 연도/월: {request.year}/{request.month}")
                    print(f"    필터 매치: {matches_filter} (연도매치: {extract_year == request.year}, 월매치: {extract_month == request.month})")

                # 해당 사용자의 캠페인 데이터 조회 (campaign.start_date 기준, 취소 캠페인 제외)
                campaign_query = select(Campaign).where(
                    and_(
                        Campaign.staff_id == user.id,
                        extract('year', Campaign.start_date) == request.year,
                        extract('month', Campaign.start_date) == request.month,
                        Campaign.status != CampaignStatus.CANCELLED
                    )
                ).options(
                    selectinload(Campaign.posts).selectinload(Post.product)
                )

                campaigns_result = await db.execute(campaign_query)
                campaigns = campaigns_result.scalars().all()

                print(f"[MONTHLY-INCENTIVE] SQL 필터링 결과: {len(campaigns)}개 캠페인 발견")
                for campaign in campaigns:
                    print(f"  - 캠페인 {campaign.id}: {campaign.name}, 시작일: {campaign.start_date}")

                # 매출/이익 계산
                total_revenue = 0.0
                total_cost = 0.0
                campaign_count = len(campaigns)

                for campaign in campaigns:
                    # 매출 (캠페인 예산 - 환불액)
                    campaign_revenue = campaign.budget or 0.0
                    campaign_refund = float(campaign.refund_amount or 0) if hasattr(campaign, 'refund_amount') else 0.0
                    total_revenue += (campaign_revenue - campaign_refund)

                    # 원가 계산 (취소되지 않은 post만)
                    campaign_cost = 0.0
                    for post in campaign.posts:
                        if getattr(post, 'is_cancelled', False):
                            continue
                        if post.product and post.product.cost:
                            post_cost = post.product.cost * (post.quantity or 1)
                            campaign_cost += post_cost

                    total_cost += campaign_cost

                total_profit = total_revenue - total_cost

                # 인센티브 계산 (이익 기준)
                incentive_rate = user.incentive_rate or 0.0
                profit_incentive = total_profit * (incentive_rate / 100.0)

                # 기존 조정금액 보존 (재계산 시)
                adjustment_amount = 0.0
                bonus_amount = 0.0
                if existing_incentive:
                    adjustment_amount = existing_incentive.adjustment_amount or 0.0
                    bonus_amount = existing_incentive.bonus_amount or 0.0

                final_amount = profit_incentive + adjustment_amount + bonus_amount

                if existing_incentive:
                    # 기존 데이터 업데이트
                    existing_incentive.total_revenue = total_revenue
                    existing_incentive.total_profit = total_profit
                    existing_incentive.campaign_count = campaign_count
                    existing_incentive.incentive_rate = incentive_rate
                    existing_incentive.profit_incentive_amount = profit_incentive
                    existing_incentive.final_incentive_amount = final_amount
                    existing_incentive.notes = f"{campaign_count}개 캠페인 기준, 매출: {total_revenue:,.0f}원, 이익: {total_profit:,.0f}원"
                    existing_incentive.status = IncentiveStatus.CALCULATED

                    results.append(IncentiveCalculationResult(
                        user_id=user.id,
                        user_name=user.name,
                        company=user.company or "미설정",
                        status="updated",
                        message="인센티브 재계산 완료",
                        incentive_amount=final_amount
                    ))
                    summary["updated"] += 1
                else:
                    # 새 데이터 생성
                    new_incentive = MonthlyIncentive(
                        user_id=user.id,
                        year=request.year,
                        month=request.month,
                        company=user.company,
                        total_revenue=total_revenue,
                        total_profit=total_profit,
                        campaign_count=campaign_count,
                        incentive_rate=incentive_rate,
                        base_incentive_amount=0.0,
                        profit_incentive_amount=profit_incentive,
                        adjustment_amount=0.0,
                        bonus_amount=0.0,
                        final_incentive_amount=profit_incentive,
                        status=IncentiveStatus.CALCULATED,
                        notes=f"{campaign_count}개 캠페인 기준, 매출: {total_revenue:,.0f}원, 이익: {total_profit:,.0f}원"
                    )
                    db.add(new_incentive)

                    results.append(IncentiveCalculationResult(
                        user_id=user.id,
                        user_name=user.name,
                        company=user.company or "미설정",
                        status="created",
                        message="인센티브 계산 완료",
                        incentive_amount=profit_incentive
                    ))
                    summary["created"] += 1

            except Exception as e:
                logger.error(f"사용자 {user.name}({user.id}) 인센티브 계산 실패: {str(e)}")
                results.append(IncentiveCalculationResult(
                    user_id=user.id,
                    user_name=user.name,
                    company=user.company or "미설정",
                    status="error",
                    message=f"계산 오류: {str(e)}",
                    incentive_amount=0.0
                ))
                summary["error"] += 1

        # 데이터베이스 커밋
        await db.commit()

        logger.info(f"인센티브 계산 완료: {summary}")

        return IncentiveCalculationResponse(
            success=True,
            total_processed=len(target_users),
            results=results,
            summary=summary
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"인센티브 계산 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"인센티브 계산 실패: {str(e)}")

@router.get("/", response_model=List[MonthlyIncentiveResponse])
async def get_monthly_incentives(
    year: Optional[int] = Query(None, description="연도"),
    month: Optional[int] = Query(None, description="월"),
    company: Optional[str] = Query(None, description="회사명"),
    status: Optional[IncentiveStatus] = Query(None, description="상태"),
    user_id: Optional[int] = Query(None, description="사용자 ID"),
    limit: int = Query(100, ge=1, le=1000, description="조회 제한"),
    offset: int = Query(0, ge=0, description="조회 오프셋"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """월간 인센티브 목록 조회"""

    # 권한 확인 - STAFF는 본인 데이터만 조회 가능
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN, UserRole.STAFF]:
        raise HTTPException(status_code=403, detail="권한이 없습니다")

    try:
        # 기본 쿼리 설정
        query = select(MonthlyIncentive).options(
            selectinload(MonthlyIncentive.user),
            selectinload(MonthlyIncentive.approver)
        )

        # 권한별 필터링
        if current_user.role == UserRole.STAFF:
            # 직원은 본인 데이터만
            query = query.where(MonthlyIncentive.user_id == current_user.id)
        elif current_user.role == UserRole.AGENCY_ADMIN:
            # 대행사 어드민은 자신 회사 직원들만
            query = query.where(MonthlyIncentive.company == current_user.company)

        # 조건별 필터링
        if year:
            query = query.where(MonthlyIncentive.year == year)
        if month:
            query = query.where(MonthlyIncentive.month == month)
        if company and current_user.role == UserRole.SUPER_ADMIN:
            # 슈퍼 어드민만 회사 필터 사용 가능
            query = query.where(MonthlyIncentive.company == company)
        if status:
            query = query.where(MonthlyIncentive.status == status)
        if user_id:
            # 권한 확인
            if current_user.role == UserRole.STAFF and user_id != current_user.id:
                raise HTTPException(status_code=403, detail="본인의 데이터만 조회할 수 있습니다")
            query = query.where(MonthlyIncentive.user_id == user_id)

        # 정렬 및 페이징
        query = query.order_by(
            desc(MonthlyIncentive.year),
            desc(MonthlyIncentive.month),
            MonthlyIncentive.user_id
        ).offset(offset).limit(limit)

        # 쿼리 실행
        result = await db.execute(query)
        incentives = result.scalars().all()

        # 응답 데이터 변환
        response_data = []
        for incentive in incentives:
            incentive_dict = {
                "id": incentive.id,
                "user_id": incentive.user_id,
                "year": incentive.year,
                "month": incentive.month,
                "company": incentive.company,
                "total_revenue": incentive.total_revenue,
                "total_profit": incentive.total_profit,
                "campaign_count": incentive.campaign_count,
                "incentive_rate": incentive.incentive_rate,
                "base_incentive_amount": incentive.base_incentive_amount,
                "profit_incentive_amount": incentive.profit_incentive_amount,
                "adjustment_amount": incentive.adjustment_amount,
                "bonus_amount": incentive.bonus_amount,
                "final_incentive_amount": incentive.final_incentive_amount,
                "status": incentive.status,
                "notes": incentive.notes,
                "adjustment_reason": incentive.adjustment_reason,
                "approved_by": incentive.approved_by,
                "approved_at": incentive.approved_at,
                "paid_at": incentive.paid_at,
                "created_at": incentive.created_at,
                "updated_at": incentive.updated_at
            }

            # 사용자 정보 추가
            if incentive.user:
                incentive_dict["user"] = {
                    "id": incentive.user.id,
                    "name": incentive.user.name,
                    "email": incentive.user.email,
                    "company": incentive.user.company,
                    "role": incentive.user.role,
                    "incentive_rate": incentive.user.incentive_rate
                }

            # 승인자 정보 추가
            if incentive.approver:
                incentive_dict["approver"] = {
                    "id": incentive.approver.id,
                    "name": incentive.approver.name,
                    "email": incentive.approver.email
                }

            response_data.append(MonthlyIncentiveResponse(**incentive_dict))

        logger.info(f"인센티브 목록 조회 완료: {len(response_data)}건")
        return response_data

    except Exception as e:
        logger.error(f"인센티브 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"조회 실패: {str(e)}")

@router.get("/stats", response_model=IncentiveStatsResponse)
async def get_incentive_stats(
    year: Optional[int] = Query(None, description="연도"),
    month: Optional[int] = Query(None, description="월"),
    company: Optional[str] = Query(None, description="회사명"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """월간 인센티브 통계 조회"""

    # 권한 확인
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다")

    # 임시 기본 통계 반환 - 실제 통계 로직은 추후 구현
    return IncentiveStatsResponse(
        total_employees=0,
        pending_incentives=0,
        approved_incentives=0,
        paid_incentives=0,
        total_incentive_amount=0.0,
        total_adjustment_amount=0.0,
        total_bonus_amount=0.0,
        total_final_amount=0.0,
        companies=[]
    )

@router.put("/{incentive_id}", response_model=MonthlyIncentiveResponse)
async def update_monthly_incentive(
    incentive_id: int,
    update_data: MonthlyIncentiveUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """월간 인센티브 수정 (조정금액, 상태 등)"""

    # 권한 확인
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다")

    try:
        # 기존 인센티브 조회
        query = select(MonthlyIncentive).where(MonthlyIncentive.id == incentive_id).options(
            selectinload(MonthlyIncentive.user),
            selectinload(MonthlyIncentive.approver)
        )

        result = await db.execute(query)
        incentive = result.scalar_one_or_none()

        if not incentive:
            raise HTTPException(status_code=404, detail="인센티브 데이터를 찾을 수 없습니다")

        # 권한 확인 (대행사 어드민은 자신 회사만)
        if current_user.role == UserRole.AGENCY_ADMIN:
            if incentive.company != current_user.company:
                raise HTTPException(status_code=403, detail="권한이 없습니다")

        # 업데이트할 필드들 적용
        update_fields = update_data.model_dump(exclude_unset=True)

        for field, value in update_fields.items():
            if hasattr(incentive, field):
                setattr(incentive, field, value)

        # 상태 변경 시 승인 정보 업데이트
        if "status" in update_fields:
            if update_data.status == IncentiveStatus.APPROVED:
                incentive.approved_by = current_user.id
                incentive.approved_at = datetime.now().isoformat()
            elif update_data.status == IncentiveStatus.PAID:
                if not incentive.approved_by:
                    incentive.approved_by = current_user.id
                    incentive.approved_at = datetime.now().isoformat()
                incentive.paid_at = datetime.now().isoformat()

        # 최종 금액 재계산
        incentive.calculate_final_amount()

        await db.commit()
        await db.refresh(incentive)

        # 응답 데이터 변환
        incentive_dict = {
            "id": incentive.id,
            "user_id": incentive.user_id,
            "year": incentive.year,
            "month": incentive.month,
            "company": incentive.company,
            "total_revenue": incentive.total_revenue,
            "total_profit": incentive.total_profit,
            "campaign_count": incentive.campaign_count,
            "incentive_rate": incentive.incentive_rate,
            "base_incentive_amount": incentive.base_incentive_amount,
            "profit_incentive_amount": incentive.profit_incentive_amount,
            "adjustment_amount": incentive.adjustment_amount,
            "bonus_amount": incentive.bonus_amount,
            "final_incentive_amount": incentive.final_incentive_amount,
            "status": incentive.status,
            "notes": incentive.notes,
            "adjustment_reason": incentive.adjustment_reason,
            "approved_by": incentive.approved_by,
            "approved_at": incentive.approved_at,
            "paid_at": incentive.paid_at,
            "created_at": incentive.created_at,
            "updated_at": incentive.updated_at
        }

        # 사용자 정보 추가
        if incentive.user:
            incentive_dict["user"] = {
                "id": incentive.user.id,
                "name": incentive.user.name,
                "email": incentive.user.email,
                "company": incentive.user.company,
                "role": incentive.user.role,
                "incentive_rate": incentive.user.incentive_rate
            }

        # 승인자 정보 추가
        if incentive.approver:
            incentive_dict["approver"] = {
                "id": incentive.approver.id,
                "name": incentive.approver.name,
                "email": incentive.approver.email
            }

        logger.info(f"인센티브 수정 완료: ID {incentive_id}")
        return MonthlyIncentiveResponse(**incentive_dict)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"인센티브 수정 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"수정 실패: {str(e)}")

@router.delete("/{incentive_id}")
async def delete_monthly_incentive(
    incentive_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """월간 인센티브 삭제"""

    # 권한 확인
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다")

    raise HTTPException(status_code=501, detail="아직 구현되지 않은 기능입니다")