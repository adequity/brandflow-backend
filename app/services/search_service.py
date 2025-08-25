"""
고급 검색 및 필터링 서비스
전문 검색, 다중 필터, 정렬, 페이징 기능 제공
"""

from typing import List, Dict, Any, Optional, Union, Tuple
from sqlalchemy import select, and_, or_, desc, asc, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from datetime import datetime, timedelta
from enum import Enum
import re
import logging

from app.models.campaign import Campaign
from app.models.purchase_request import PurchaseRequest, RequestStatus
from app.models.user import User

logger = logging.getLogger(__name__)

class SortOrder(str, Enum):
    """정렬 순서"""
    ASC = "asc"
    DESC = "desc"

class SearchOperator(str, Enum):
    """검색 연산자"""
    EQUALS = "equals"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "gt"
    GREATER_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_EQUAL = "lte"
    BETWEEN = "between"
    IN = "in"
    NOT_IN = "not_in"

class SearchService:
    """고급 검색 및 필터링 서비스"""
    
    def __init__(self):
        # 캠페인 검색 가능 필드 정의
        self.campaign_searchable_fields = {
            'name': {'type': 'text', 'operators': ['contains', 'starts_with', 'ends_with', 'equals']},
            'description': {'type': 'text', 'operators': ['contains']},
            'client_company': {'type': 'text', 'operators': ['contains', 'starts_with', 'equals']},
            'status': {'type': 'enum', 'operators': ['equals', 'in', 'not_in']},
            'budget': {'type': 'number', 'operators': ['equals', 'gt', 'gte', 'lt', 'lte', 'between']},
            'start_date': {'type': 'date', 'operators': ['equals', 'gt', 'gte', 'lt', 'lte', 'between']},
            'end_date': {'type': 'date', 'operators': ['equals', 'gt', 'gte', 'lt', 'lte', 'between']},
            'created_at': {'type': 'datetime', 'operators': ['equals', 'gt', 'gte', 'lt', 'lte', 'between']},
            'updated_at': {'type': 'datetime', 'operators': ['equals', 'gt', 'gte', 'lt', 'lte', 'between']}
        }
        
        # 구매요청 검색 가능 필드 정의
        self.purchase_request_searchable_fields = {
            'title': {'type': 'text', 'operators': ['contains', 'starts_with', 'ends_with', 'equals']},
            'description': {'type': 'text', 'operators': ['contains']},
            'category': {'type': 'enum', 'operators': ['equals', 'in', 'not_in']},
            'status': {'type': 'enum', 'operators': ['equals', 'in', 'not_in']},
            'urgency': {'type': 'enum', 'operators': ['equals', 'in', 'not_in']},
            'quantity': {'type': 'number', 'operators': ['equals', 'gt', 'gte', 'lt', 'lte', 'between']},
            'unit_price': {'type': 'number', 'operators': ['equals', 'gt', 'gte', 'lt', 'lte', 'between']},
            'total_amount': {'type': 'number', 'operators': ['equals', 'gt', 'gte', 'lt', 'lte', 'between']},
            'created_at': {'type': 'datetime', 'operators': ['equals', 'gt', 'gte', 'lt', 'lte', 'between']},
            'updated_at': {'type': 'datetime', 'operators': ['equals', 'gt', 'gte', 'lt', 'lte', 'between']}
        }
    
    def build_text_condition(self, field, operator: str, value: str):
        """텍스트 필드 조건 생성"""
        if operator == SearchOperator.EQUALS:
            return field == value
        elif operator == SearchOperator.CONTAINS:
            return field.ilike(f"%{value}%")
        elif operator == SearchOperator.STARTS_WITH:
            return field.ilike(f"{value}%")
        elif operator == SearchOperator.ENDS_WITH:
            return field.ilike(f"%{value}")
        else:
            raise ValueError(f"Unsupported text operator: {operator}")
    
    def build_number_condition(self, field, operator: str, value: Union[int, float, List]):
        """숫자 필드 조건 생성"""
        if operator == SearchOperator.EQUALS:
            return field == value
        elif operator == SearchOperator.GREATER_THAN:
            return field > value
        elif operator == SearchOperator.GREATER_EQUAL:
            return field >= value
        elif operator == SearchOperator.LESS_THAN:
            return field < value
        elif operator == SearchOperator.LESS_EQUAL:
            return field <= value
        elif operator == SearchOperator.BETWEEN:
            if len(value) != 2:
                raise ValueError("Between operator requires exactly 2 values")
            return and_(field >= value[0], field <= value[1])
        elif operator == SearchOperator.IN:
            return field.in_(value)
        elif operator == SearchOperator.NOT_IN:
            return ~field.in_(value)
        else:
            raise ValueError(f"Unsupported number operator: {operator}")
    
    def build_date_condition(self, field, operator: str, value: Union[str, datetime, List]):
        """날짜 필드 조건 생성"""
        # 문자열을 datetime으로 변환
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except:
                value = datetime.strptime(value, '%Y-%m-%d')
        elif isinstance(value, list):
            converted_values = []
            for v in value:
                if isinstance(v, str):
                    try:
                        converted_values.append(datetime.fromisoformat(v.replace('Z', '+00:00')))
                    except:
                        converted_values.append(datetime.strptime(v, '%Y-%m-%d'))
                else:
                    converted_values.append(v)
            value = converted_values
        
        return self.build_number_condition(field, operator, value)
    
    def build_enum_condition(self, field, operator: str, value: Union[str, List]):
        """열거형 필드 조건 생성"""
        if operator == SearchOperator.EQUALS:
            return field == value
        elif operator == SearchOperator.IN:
            return field.in_(value if isinstance(value, list) else [value])
        elif operator == SearchOperator.NOT_IN:
            return ~field.in_(value if isinstance(value, list) else [value])
        else:
            raise ValueError(f"Unsupported enum operator: {operator}")
    
    def build_filter_conditions(self, model_class, filters: List[Dict[str, Any]], searchable_fields: Dict):
        """필터 조건들을 SQLAlchemy 조건으로 변환"""
        conditions = []
        
        for filter_item in filters:
            field_name = filter_item.get('field')
            operator = filter_item.get('operator', 'equals')
            value = filter_item.get('value')
            
            if not field_name or value is None:
                continue
            
            if field_name not in searchable_fields:
                logger.warning(f"Field '{field_name}' is not searchable")
                continue
            
            field_config = searchable_fields[field_name]
            if operator not in field_config['operators']:
                logger.warning(f"Operator '{operator}' not supported for field '{field_name}'")
                continue
            
            # 모델 필드 가져오기
            field = getattr(model_class, field_name)
            
            try:
                if field_config['type'] == 'text':
                    condition = self.build_text_condition(field, operator, value)
                elif field_config['type'] == 'number':
                    condition = self.build_number_condition(field, operator, value)
                elif field_config['type'] in ['date', 'datetime']:
                    condition = self.build_date_condition(field, operator, value)
                elif field_config['type'] == 'enum':
                    condition = self.build_enum_condition(field, operator, value)
                else:
                    logger.warning(f"Unknown field type: {field_config['type']}")
                    continue
                
                conditions.append(condition)
                
            except Exception as e:
                logger.error(f"Error building condition for field '{field_name}': {e}")
                continue
        
        return conditions
    
    def apply_sorting(self, query, sort_by: Optional[str], sort_order: str, model_class, searchable_fields: Dict):
        """정렬 적용"""
        if not sort_by or sort_by not in searchable_fields:
            # 기본 정렬 (생성일 내림차순)
            return query.order_by(desc(model_class.created_at))
        
        field = getattr(model_class, sort_by)
        if sort_order == SortOrder.DESC:
            return query.order_by(desc(field))
        else:
            return query.order_by(asc(field))
    
    def apply_pagination(self, query, page: int = 1, page_size: int = 20):
        """페이징 적용"""
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        
        offset = (page - 1) * page_size
        return query.offset(offset).limit(page_size)
    
    async def search_campaigns(
        self,
        db: AsyncSession,
        query_text: Optional[str] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = SortOrder.DESC,
        page: int = 1,
        page_size: int = 20,
        include_relations: bool = True
    ) -> Tuple[List[Campaign], int]:
        """
        캠페인 고급 검색
        
        Args:
            query_text: 전체 텍스트 검색어
            filters: 상세 필터 조건들
            sort_by: 정렬 기준 필드
            sort_order: 정렬 순서 (asc/desc)
            page: 페이지 번호
            page_size: 페이지 크기
            include_relations: 관련 데이터 포함 여부
        
        Returns:
            (캠페인 리스트, 전체 개수)
        """
        try:
            # 기본 쿼리
            query = select(Campaign)
            
            # 관련 데이터 포함
            if include_relations:
                query = query.options(selectinload(Campaign.creator))
            
            # 전체 텍스트 검색
            if query_text:
                search_conditions = [
                    Campaign.name.ilike(f"%{query_text}%"),
                    Campaign.description.ilike(f"%{query_text}%"),
                    Campaign.client_company.ilike(f"%{query_text}%")
                ]
                query = query.where(or_(*search_conditions))
            
            # 상세 필터 적용
            if filters:
                filter_conditions = self.build_filter_conditions(
                    Campaign, filters, self.campaign_searchable_fields
                )
                if filter_conditions:
                    query = query.where(and_(*filter_conditions))
            
            # 전체 개수 조회 (정렬/페이징 전)
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total = total_result.scalar()
            
            # 정렬 적용
            query = self.apply_sorting(query, sort_by, sort_order, Campaign, self.campaign_searchable_fields)
            
            # 페이징 적용
            query = self.apply_pagination(query, page, page_size)
            
            # 결과 조회
            result = await db.execute(query)
            campaigns = result.scalars().all()
            
            return campaigns, total
            
        except Exception as e:
            logger.error(f"Campaign search failed: {e}")
            raise
    
    async def search_purchase_requests(
        self,
        db: AsyncSession,
        query_text: Optional[str] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = SortOrder.DESC,
        page: int = 1,
        page_size: int = 20,
        include_relations: bool = True
    ) -> Tuple[List[PurchaseRequest], int]:
        """
        구매요청 고급 검색
        
        Args:
            query_text: 전체 텍스트 검색어
            filters: 상세 필터 조건들
            sort_by: 정렬 기준 필드
            sort_order: 정렬 순서 (asc/desc)
            page: 페이지 번호
            page_size: 페이지 크기
            include_relations: 관련 데이터 포함 여부
        
        Returns:
            (구매요청 리스트, 전체 개수)
        """
        try:
            # 기본 쿼리
            query = select(PurchaseRequest)
            
            # 관련 데이터 포함
            if include_relations:
                query = query.options(selectinload(PurchaseRequest.requester))
            
            # 전체 텍스트 검색
            if query_text:
                search_conditions = [
                    PurchaseRequest.title.ilike(f"%{query_text}%"),
                    PurchaseRequest.description.ilike(f"%{query_text}%"),
                    PurchaseRequest.category.ilike(f"%{query_text}%")
                ]
                query = query.where(or_(*search_conditions))
            
            # 상세 필터 적용
            if filters:
                filter_conditions = self.build_filter_conditions(
                    PurchaseRequest, filters, self.purchase_request_searchable_fields
                )
                if filter_conditions:
                    query = query.where(and_(*filter_conditions))
            
            # 전체 개수 조회 (정렬/페이징 전)
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total = total_result.scalar()
            
            # 정렬 적용
            query = self.apply_sorting(query, sort_by, sort_order, PurchaseRequest, self.purchase_request_searchable_fields)
            
            # 페이징 적용
            query = self.apply_pagination(query, page, page_size)
            
            # 결과 조회
            result = await db.execute(query)
            requests = result.scalars().all()
            
            return requests, total
            
        except Exception as e:
            logger.error(f"Purchase request search failed: {e}")
            raise
    
    async def get_search_suggestions(
        self,
        db: AsyncSession,
        model_type: str,
        field: str,
        query: str,
        limit: int = 10
    ) -> List[str]:
        """
        검색 자동완성 제안
        
        Args:
            model_type: 모델 타입 (campaigns/purchase_requests)
            field: 검색할 필드명
            query: 검색어
            limit: 최대 제안 개수
        
        Returns:
            제안 문자열 리스트
        """
        try:
            if model_type == "campaigns":
                model_class = Campaign
                searchable_fields = self.campaign_searchable_fields
            elif model_type == "purchase_requests":
                model_class = PurchaseRequest
                searchable_fields = self.purchase_request_searchable_fields
            else:
                return []
            
            if field not in searchable_fields:
                return []
            
            field_config = searchable_fields[field]
            if field_config['type'] != 'text':
                return []
            
            # 필드에서 유사한 값들 조회
            model_field = getattr(model_class, field)
            query_stmt = select(model_field).where(
                and_(
                    model_field.ilike(f"%{query}%"),
                    model_field.is_not(None)
                )
            ).distinct().limit(limit)
            
            result = await db.execute(query_stmt)
            suggestions = [row[0] for row in result.fetchall() if row[0]]
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Get search suggestions failed: {e}")
            return []
    
    def get_searchable_fields(self, model_type: str) -> Dict[str, Any]:
        """검색 가능 필드 목록 반환"""
        if model_type == "campaigns":
            return self.campaign_searchable_fields
        elif model_type == "purchase_requests":
            return self.purchase_request_searchable_fields
        else:
            return {}

# 전역 검색 서비스 인스턴스
search_service = SearchService()