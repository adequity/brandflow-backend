"""
고급 검색 및 필터링 엔드포인트
전문 검색, 다중 필터, 정렬, 페이징 기능 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

from app.db.database import get_async_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.services.search_service import search_service, SortOrder
from app.schemas.campaign import CampaignResponse
from app.schemas.purchase_request import PurchaseRequestResponse
from datetime import datetime

router = APIRouter()

class FilterCondition(BaseModel):
    """필터 조건 스키마"""
    field: str = Field(..., description="필터링할 필드명")
    operator: str = Field(..., description="연산자 (equals, contains, gt, lt, between, in, etc.)")
    value: Any = Field(..., description="필터 값")

class SearchRequest(BaseModel):
    """검색 요청 스키마"""
    query_text: Optional[str] = Field(None, description="전체 텍스트 검색어")
    filters: Optional[List[FilterCondition]] = Field(None, description="상세 필터 조건들")
    sort_by: Optional[str] = Field(None, description="정렬 기준 필드")
    sort_order: SortOrder = Field(SortOrder.DESC, description="정렬 순서")
    page: int = Field(1, ge=1, description="페이지 번호")
    page_size: int = Field(20, ge=1, le=100, description="페이지 크기")
    include_relations: bool = Field(True, description="관련 데이터 포함 여부")

class SearchResponse(BaseModel):
    """검색 응답 스키마"""
    data: List[Any] = Field(..., description="검색 결과 데이터")
    total: int = Field(..., description="전체 결과 수")
    page: int = Field(..., description="현재 페이지")
    page_size: int = Field(..., description="페이지 크기")
    total_pages: int = Field(..., description="전체 페이지 수")
    has_next: bool = Field(..., description="다음 페이지 존재 여부")
    has_previous: bool = Field(..., description="이전 페이지 존재 여부")

@router.post("/campaigns", response_model=SearchResponse)
async def search_campaigns(
    search_request: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    캠페인 고급 검색
    
    ## 검색 기능
    - **전체 텍스트 검색**: 캠페인명, 설명, 클라이언트사에서 검색
    - **상세 필터**: 필드별 정확한 조건 설정
    - **정렬**: 모든 필드에 대한 오름차순/내림차순 정렬
    - **페이징**: 효율적인 대량 데이터 처리
    
    ## 필터 예시
    ```json
    {
      "query_text": "마케팅",
      "filters": [
        {"field": "status", "operator": "equals", "value": "ACTIVE"},
        {"field": "budget", "operator": "gte", "value": 1000000},
        {"field": "start_date", "operator": "between", "value": ["2024-01-01", "2024-12-31"]}
      ],
      "sort_by": "created_at",
      "sort_order": "desc",
      "page": 1,
      "page_size": 20
    }
    ```
    """
    try:
        # 필터 조건 변환
        filters = None
        if search_request.filters:
            filters = [filter_item.model_dump() for filter_item in search_request.filters]
        
        # 검색 실행
        campaigns, total = await search_service.search_campaigns(
            db=db,
            query_text=search_request.query_text,
            filters=filters,
            sort_by=search_request.sort_by,
            sort_order=search_request.sort_order,
            page=search_request.page,
            page_size=search_request.page_size,
            include_relations=search_request.include_relations
        )
        
        # 페이징 정보 계산
        total_pages = (total + search_request.page_size - 1) // search_request.page_size
        has_next = search_request.page < total_pages
        has_previous = search_request.page > 1
        
        # 응답 데이터 변환
        campaign_data = []
        for campaign in campaigns:
            campaign_dict = {
                'id': campaign.id,
                'name': campaign.name,
                'description': campaign.description,
                'client_company': campaign.client_company,
                'budget': campaign.budget,
                'status': campaign.status,
                'start_date': campaign.start_date.isoformat() if campaign.start_date else None,
                'end_date': campaign.end_date.isoformat() if campaign.end_date else None,
                'created_at': campaign.created_at.isoformat() if campaign.created_at else None,
                'updated_at': campaign.updated_at.isoformat() if campaign.updated_at else None,
                'creator_id': campaign.creator_id
            }
            
            if search_request.include_relations and campaign.creator:
                campaign_dict['creator'] = {
                    'id': campaign.creator.id,
                    'username': campaign.creator.username,
                    'role': campaign.creator.role
                }
            
            campaign_data.append(campaign_dict)
        
        return SearchResponse(
            data=campaign_data,
            total=total,
            page=search_request.page,
            page_size=search_request.page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"캠페인 검색 실패: {str(e)}")

@router.post("/purchase-requests", response_model=SearchResponse)
async def search_purchase_requests(
    search_request: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    구매요청 고급 검색
    
    ## 검색 기능
    - **전체 텍스트 검색**: 제목, 설명, 카테고리에서 검색
    - **상세 필터**: 상태, 긴급도, 가격 범위 등 정확한 조건 설정
    - **정렬**: 모든 필드에 대한 오름차순/내림차순 정렬
    - **페이징**: 효율적인 대량 데이터 처리
    
    ## 필터 예시
    ```json
    {
      "query_text": "사무용품",
      "filters": [
        {"field": "status", "operator": "in", "value": ["PENDING", "APPROVED"]},
        {"field": "urgency", "operator": "equals", "value": "HIGH"},
        {"field": "total_amount", "operator": "between", "value": [10000, 100000]}
      ],
      "sort_by": "created_at",
      "sort_order": "desc"
    }
    ```
    """
    try:
        # 필터 조건 변환
        filters = None
        if search_request.filters:
            filters = [filter_item.model_dump() for filter_item in search_request.filters]
        
        # 검색 실행
        requests, total = await search_service.search_purchase_requests(
            db=db,
            query_text=search_request.query_text,
            filters=filters,
            sort_by=search_request.sort_by,
            sort_order=search_request.sort_order,
            page=search_request.page,
            page_size=search_request.page_size,
            include_relations=search_request.include_relations
        )
        
        # 페이징 정보 계산
        total_pages = (total + search_request.page_size - 1) // search_request.page_size
        has_next = search_request.page < total_pages
        has_previous = search_request.page > 1
        
        # 응답 데이터 변환
        request_data = []
        for request in requests:
            request_dict = {
                'id': request.id,
                'title': request.title,
                'description': request.description,
                'category': request.category,
                'quantity': request.quantity,
                'unit_price': request.unit_price,
                'total_amount': request.total_amount,
                'status': request.status,
                'urgency': request.urgency,
                'created_at': request.created_at.isoformat() if request.created_at else None,
                'updated_at': request.updated_at.isoformat() if request.updated_at else None,
                'requester_id': request.requester_id
            }
            
            if search_request.include_relations and request.requester:
                request_dict['requester'] = {
                    'id': request.requester.id,
                    'username': request.requester.username,
                    'role': request.requester.role
                }
            
            request_data.append(request_dict)
        
        return SearchResponse(
            data=request_data,
            total=total,
            page=search_request.page,
            page_size=search_request.page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"구매요청 검색 실패: {str(e)}")

@router.get("/fields/{model_type}")
async def get_searchable_fields(
    model_type: Literal["campaigns", "purchase_requests"],
    current_user: User = Depends(get_current_active_user)
):
    """
    검색 가능한 필드 목록 조회
    
    - **model_type**: 모델 타입 (campaigns, purchase_requests)
    
    각 필드의 데이터 타입과 지원되는 연산자 정보를 반환합니다.
    """
    try:
        searchable_fields = search_service.get_searchable_fields(model_type)
        
        if not searchable_fields:
            raise HTTPException(status_code=404, detail="지원되지 않는 모델 타입입니다.")
        
        return {
            "model_type": model_type,
            "searchable_fields": searchable_fields,
            "operators": {
                "text": {
                    "equals": "정확히 일치",
                    "contains": "포함",
                    "starts_with": "~로 시작",
                    "ends_with": "~로 끝남"
                },
                "number": {
                    "equals": "같음",
                    "gt": "보다 큼",
                    "gte": "보다 크거나 같음",
                    "lt": "보다 작음",
                    "lte": "보다 작거나 같음",
                    "between": "범위 내",
                    "in": "목록 중 하나",
                    "not_in": "목록에 없음"
                },
                "enum": {
                    "equals": "같음",
                    "in": "목록 중 하나",
                    "not_in": "목록에 없음"
                },
                "date": {
                    "equals": "같은 날짜",
                    "gt": "이후",
                    "gte": "이후 또는 같은 날",
                    "lt": "이전",
                    "lte": "이전 또는 같은 날",
                    "between": "기간 내"
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"필드 정보 조회 실패: {str(e)}")

@router.get("/suggestions/{model_type}")
async def get_search_suggestions(
    model_type: Literal["campaigns", "purchase_requests"],
    field: str = Query(..., description="검색할 필드명"),
    query: str = Query(..., min_length=1, description="검색어"),
    limit: int = Query(10, ge=1, le=50, description="최대 제안 개수"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    검색 자동완성 제안
    
    - **model_type**: 모델 타입 (campaigns, purchase_requests)
    - **field**: 검색할 필드명
    - **query**: 검색어 (최소 1글자)
    - **limit**: 최대 제안 개수 (1-50)
    
    입력한 검색어와 유사한 기존 데이터를 제안합니다.
    """
    try:
        suggestions = await search_service.get_search_suggestions(
            db=db,
            model_type=model_type,
            field=field,
            query=query,
            limit=limit
        )
        
        return {
            "model_type": model_type,
            "field": field,
            "query": query,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 제안 실패: {str(e)}")

@router.get("/quick")
async def quick_search(
    q: str = Query(..., min_length=1, description="검색어"),
    type: Optional[Literal["campaigns", "purchase_requests", "all"]] = Query("all", description="검색 대상"),
    limit: int = Query(5, ge=1, le=20, description="각 타입별 최대 결과 수"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    빠른 검색 (통합 검색)
    
    - **q**: 검색어
    - **type**: 검색 대상 (campaigns, purchase_requests, all)
    - **limit**: 각 타입별 최대 결과 수
    
    여러 데이터 타입에서 동시에 검색하여 통합 결과를 반환합니다.
    """
    try:
        results = {}
        
        # 캠페인 검색
        if type in ["campaigns", "all"]:
            campaigns, campaign_total = await search_service.search_campaigns(
                db=db,
                query_text=q,
                page=1,
                page_size=limit,
                include_relations=False
            )
            
            results["campaigns"] = {
                "data": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "client_company": c.client_company,
                        "status": c.status,
                        "budget": c.budget
                    }
                    for c in campaigns
                ],
                "total": campaign_total,
                "type": "campaigns"
            }
        
        # 구매요청 검색
        if type in ["purchase_requests", "all"]:
            requests, request_total = await search_service.search_purchase_requests(
                db=db,
                query_text=q,
                page=1,
                page_size=limit,
                include_relations=False
            )
            
            results["purchase_requests"] = {
                "data": [
                    {
                        "id": r.id,
                        "title": r.title,
                        "category": r.category,
                        "status": r.status,
                        "total_amount": r.total_amount
                    }
                    for r in requests
                ],
                "total": request_total,
                "type": "purchase_requests"
            }
        
        # 전체 결과 수 계산
        total_results = sum(result.get("total", 0) for result in results.values())
        
        return {
            "query": q,
            "results": results,
            "total_results": total_results,
            "search_time": "< 1s"  # 실제로는 측정할 수 있음
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"빠른 검색 실패: {str(e)}")

@router.get("/stats/{model_type}")
async def get_search_stats(
    model_type: Literal["campaigns", "purchase_requests"],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    검색 통계 정보
    
    - **model_type**: 모델 타입 (campaigns, purchase_requests)
    
    각 필드별 데이터 분포와 통계 정보를 제공합니다.
    """
    try:
        # 관리자만 통계 조회 가능
        if current_user.role not in ["admin", "슈퍼 어드민", "대행사 어드민"]:
            raise HTTPException(status_code=403, detail="통계 조회 권한이 없습니다.")
        
        stats = {}
        
        if model_type == "campaigns":
            from sqlalchemy import func
            from app.models.campaign import Campaign
            
            # 상태별 분포
            status_stats = await db.execute(
                select(Campaign.status, func.count(Campaign.id))
                .group_by(Campaign.status)
            )
            stats["status_distribution"] = {
                status: count for status, count in status_stats.fetchall()
            }
            
            # 예산 통계
            budget_stats = await db.execute(
                select(
                    func.count(Campaign.id),
                    func.avg(Campaign.budget),
                    func.min(Campaign.budget),
                    func.max(Campaign.budget)
                ).where(Campaign.budget.is_not(None))
            )
            budget_result = budget_stats.fetchone()
            if budget_result:
                stats["budget_stats"] = {
                    "count": budget_result[0],
                    "average": float(budget_result[1]) if budget_result[1] else 0,
                    "minimum": float(budget_result[2]) if budget_result[2] else 0,
                    "maximum": float(budget_result[3]) if budget_result[3] else 0
                }
        
        elif model_type == "purchase_requests":
            from app.models.purchase_request import PurchaseRequest
            
            # 상태별 분포
            status_stats = await db.execute(
                select(PurchaseRequest.status, func.count(PurchaseRequest.id))
                .group_by(PurchaseRequest.status)
            )
            stats["status_distribution"] = {
                status: count for status, count in status_stats.fetchall()
            }
            
            # 긴급도별 분포
            urgency_stats = await db.execute(
                select(PurchaseRequest.urgency, func.count(PurchaseRequest.id))
                .group_by(PurchaseRequest.urgency)
            )
            stats["urgency_distribution"] = {
                urgency: count for urgency, count in urgency_stats.fetchall()
            }
        
        return {
            "model_type": model_type,
            "statistics": stats,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")