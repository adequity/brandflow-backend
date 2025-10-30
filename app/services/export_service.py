"""
데이터 내보내기 서비스
Excel, PDF, CSV 형식으로 데이터 내보내기 기능 제공
"""

import io
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfutils
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import logging

from app.models.campaign import Campaign
from app.models.purchase_request import PurchaseRequest
from app.models.user import User
from app.core.websocket import manager

logger = logging.getLogger(__name__)

class ExportService:
    """데이터 내보내기 서비스"""

    def __init__(self):
        self.export_dir = Path("./exports")
        self.export_dir.mkdir(exist_ok=True)

        # 한글 폰트 등록
        try:
            # NanumGothic 폰트 등록 (Railway에서 설치 필요)
            font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('NanumGothic', font_path))
                self.korean_font = 'NanumGothic'
            else:
                # 폰트 없으면 기본 폰트 사용
                self.korean_font = 'Helvetica'
                logger.warning("Korean font not found, using default font")
        except Exception as e:
            logger.error(f"Failed to load Korean font: {e}")
            self.korean_font = 'Helvetica'

        # 스타일 설정 (한글 폰트 적용)
        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#2c3e50'),
            fontName=self.korean_font
        )

        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=12,
            textColor=colors.HexColor('#34495e'),
            fontName=self.korean_font
        )

        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName=self.korean_font
        )
    
    async def export_campaigns_excel(self, campaigns: List[Campaign], user_id: int) -> str:
        """캠페인 데이터를 Excel로 내보내기"""
        try:
            # 데이터 준비
            data = []
            for campaign in campaigns:
                data.append({
                    'ID': campaign.id,
                    '캠페인명': campaign.name,
                    '설명': campaign.description or '',
                    '클라이언트': campaign.client_company or '',
                    '예산': campaign.budget or 0,
                    '시작일': campaign.start_date.strftime('%Y-%m-%d') if campaign.start_date else '',
                    '종료일': campaign.end_date.strftime('%Y-%m-%d') if campaign.end_date else '',
                    '상태': campaign.status,
                    '생성일': campaign.created_at.strftime('%Y-%m-%d %H:%M:%S') if campaign.created_at else ''
                })
            
            # DataFrame 생성
            df = pd.DataFrame(data)
            
            # 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"campaigns_export_{timestamp}.xlsx"
            filepath = self.export_dir / filename
            
            # Excel 파일 생성
            with pd.ExcelWriter(str(filepath), engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='캠페인 목록', index=False)
                
                # 워크시트 포맷팅
                worksheet = writer.sheets['캠페인 목록']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # 성공 알림
            await manager.send_to_user(user_id, {
                "type": "export_success",
                "title": "Excel 내보내기 완료",
                "message": f"캠페인 데이터가 Excel 파일로 생성되었습니다: {filename}",
                "data": {"filename": filename, "filepath": str(filepath)}
            })
            
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            await manager.send_to_user(user_id, {
                "type": "export_error",
                "title": "Excel 내보내기 실패",
                "message": f"Excel 파일 생성 중 오류가 발생했습니다: {str(e)}",
                "severity": "error"
            })
            raise
    
    async def export_purchase_requests_excel(self, requests: List[PurchaseRequest], user_id: int) -> str:
        """구매요청 데이터를 Excel로 내보내기"""
        try:
            # 데이터 준비
            data = []
            for req in requests:
                data.append({
                    'ID': req.id,
                    '제목': req.title,
                    '설명': req.description or '',
                    '카테고리': req.category,
                    '수량': req.quantity,
                    '단가': req.unit_price or 0,
                    '총액': req.total_amount or 0,
                    '상태': req.status,
                    '긴급도': req.urgency,
                    '요청자': req.requester.username if req.requester else '',
                    '요청일': req.created_at.strftime('%Y-%m-%d %H:%M:%S') if req.created_at else '',
                    '업데이트일': req.updated_at.strftime('%Y-%m-%d %H:%M:%S') if req.updated_at else ''
                })
            
            # DataFrame 생성
            df = pd.DataFrame(data)
            
            # 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"purchase_requests_export_{timestamp}.xlsx"
            filepath = self.export_dir / filename
            
            # Excel 파일 생성
            with pd.ExcelWriter(str(filepath), engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='구매요청 목록', index=False)
                
                # 워크시트 포맷팅
                worksheet = writer.sheets['구매요청 목록']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # 성공 알림
            await manager.send_to_user(user_id, {
                "type": "export_success",
                "title": "Excel 내보내기 완료",
                "message": f"구매요청 데이터가 Excel 파일로 생성되었습니다: {filename}",
                "data": {"filename": filename, "filepath": str(filepath)}
            })
            
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            await manager.send_to_user(user_id, {
                "type": "export_error",
                "title": "Excel 내보내기 실패",
                "message": f"Excel 파일 생성 중 오류가 발생했습니다: {str(e)}",
                "severity": "error"
            })
            raise
    
    async def export_campaigns_pdf(self, campaigns: List[Campaign], user_id: int) -> str:
        """캠페인 데이터를 PDF로 내보내기"""
        try:
            # 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"campaigns_report_{timestamp}.pdf"
            filepath = self.export_dir / filename
            
            # PDF 문서 생성
            doc = SimpleDocTemplate(str(filepath), pagesize=A4)
            story = []
            
            # 제목
            title = Paragraph("캠페인 리포트", self.title_style)
            story.append(title)
            story.append(Spacer(1, 20))
            
            # 생성 정보
            generated_info = Paragraph(f"생성일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')}", self.styles['Normal'])
            story.append(generated_info)
            story.append(Spacer(1, 20))
            
            # 요약 정보
            total_campaigns = len(campaigns)
            total_budget = sum(campaign.budget or 0 for campaign in campaigns)
            active_campaigns = len([c for c in campaigns if c.status == 'ACTIVE'])
            
            summary = Paragraph("요약 정보", self.heading_style)
            story.append(summary)
            
            summary_data = [
                ['전체 캠페인 수', str(total_campaigns)],
                ['활성 캠페인 수', str(active_campaigns)],
                ['총 예산', f"{total_budget:,.0f}원"],
                ['평균 예산', f"{total_budget/total_campaigns if total_campaigns > 0 else 0:,.0f}원"]
            ]
            
            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 30))
            
            # 캠페인 목록
            campaigns_heading = Paragraph("캠페인 상세 목록", self.heading_style)
            story.append(campaigns_heading)
            
            # 테이블 데이터 준비
            table_data = [['ID', '캠페인명', '클라이언트', '예산', '상태', '시작일']]
            
            for campaign in campaigns:
                table_data.append([
                    str(campaign.id),
                    campaign.name[:20] + '...' if len(campaign.name) > 20 else campaign.name,
                    campaign.client_company[:15] + '...' if campaign.client_company and len(campaign.client_company) > 15 else (campaign.client_company or ''),
                    f"{campaign.budget:,.0f}" if campaign.budget else '0',
                    campaign.status,
                    campaign.start_date.strftime('%Y-%m-%d') if campaign.start_date else ''
                ])
            
            # 테이블 생성
            table = Table(table_data, colWidths=[0.5*inch, 2*inch, 1.5*inch, 1*inch, 0.8*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(table)
            
            # PDF 빌드
            doc.build(story)
            
            # 성공 알림
            await manager.send_to_user(user_id, {
                "type": "export_success",
                "title": "PDF 내보내기 완료",
                "message": f"캠페인 리포트가 PDF 파일로 생성되었습니다: {filename}",
                "data": {"filename": filename, "filepath": str(filepath)}
            })
            
            return str(filepath)
            
        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            await manager.send_to_user(user_id, {
                "type": "export_error",
                "title": "PDF 내보내기 실패",
                "message": f"PDF 파일 생성 중 오류가 발생했습니다: {str(e)}",
                "severity": "error"
            })
            raise
    
    async def export_csv(self, data: List[Dict[str, Any]], filename_prefix: str, user_id: int) -> str:
        """일반 데이터를 CSV로 내보내기"""
        try:
            if not data:
                raise ValueError("내보낼 데이터가 없습니다.")
            
            # DataFrame 생성
            df = pd.DataFrame(data)
            
            # 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{filename_prefix}_{timestamp}.csv"
            filepath = self.export_dir / filename
            
            # CSV 파일 생성 (UTF-8 with BOM for Excel compatibility)
            df.to_csv(str(filepath), index=False, encoding='utf-8-sig')
            
            # 성공 알림
            await manager.send_to_user(user_id, {
                "type": "export_success",
                "title": "CSV 내보내기 완료",
                "message": f"데이터가 CSV 파일로 생성되었습니다: {filename}",
                "data": {"filename": filename, "filepath": str(filepath)}
            })
            
            return str(filepath)
            
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            await manager.send_to_user(user_id, {
                "type": "export_error",
                "title": "CSV 내보내기 실패",
                "message": f"CSV 파일 생성 중 오류가 발생했습니다: {str(e)}",
                "severity": "error"
            })
            raise
    
    async def create_dashboard_report_pdf(self, dashboard_data: Dict[str, Any], user_id: int) -> str:
        """대시보드 데이터를 종합 리포트 PDF로 생성"""
        try:
            # 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"dashboard_report_{timestamp}.pdf"
            filepath = self.export_dir / filename
            
            # PDF 문서 생성
            doc = SimpleDocTemplate(str(filepath), pagesize=A4)
            story = []
            
            # 제목
            title = Paragraph("BrandFlow 대시보드 리포트", self.title_style)
            story.append(title)
            story.append(Spacer(1, 20))
            
            # 생성 정보
            generated_info = Paragraph(f"생성일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')}", self.styles['Normal'])
            story.append(generated_info)
            story.append(Spacer(1, 30))
            
            # 전체 요약
            if 'summary' in dashboard_data:
                summary = dashboard_data['summary']
                summary_heading = Paragraph("전체 요약", self.heading_style)
                story.append(summary_heading)
                
                summary_data = [
                    ['전체 캠페인', str(summary.get('total_campaigns', 0))],
                    ['활성 캠페인', str(summary.get('active_campaigns', 0))],
                    ['완료된 캠페인', str(summary.get('completed_campaigns', 0))],
                    ['총 예산', f"{summary.get('total_budget', 0):,.0f}원"],
                    ['구매요청 수', str(summary.get('total_requests', 0))],
                    ['처리 대기중', str(summary.get('pending_requests', 0))]
                ]
                
                summary_table = Table(summary_data, colWidths=[2.5*inch, 2*inch])
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(summary_table)
                story.append(Spacer(1, 30))
            
            # 최근 활동
            if 'recent_activities' in dashboard_data:
                activities = dashboard_data['recent_activities']
                activities_heading = Paragraph("최근 활동", self.heading_style)
                story.append(activities_heading)
                
                for activity in activities[:10]:  # 최대 10개
                    activity_text = f"• {activity.get('description', '')}"
                    activity_para = Paragraph(activity_text, self.styles['Normal'])
                    story.append(activity_para)
                
                story.append(Spacer(1, 30))
            
            # 성능 지표
            if 'performance_metrics' in dashboard_data:
                metrics = dashboard_data['performance_metrics']
                metrics_heading = Paragraph("성능 지표", self.heading_style)
                story.append(metrics_heading)
                
                metrics_data = [
                    ['지표명', '값', '상태']
                ]
                
                for metric_name, metric_data in metrics.items():
                    status = "정상" if metric_data.get('status') == 'healthy' else "주의"
                    metrics_data.append([
                        metric_name,
                        str(metric_data.get('value', 'N/A')),
                        status
                    ])
                
                metrics_table = Table(metrics_data, colWidths=[2*inch, 1.5*inch, 1*inch])
                metrics_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                ]))
                
                story.append(metrics_table)
            
            # PDF 빌드
            doc.build(story)
            
            # 성공 알림
            await manager.send_to_user(user_id, {
                "type": "export_success",
                "title": "대시보드 리포트 생성 완료",
                "message": f"대시보드 종합 리포트가 PDF 파일로 생성되었습니다: {filename}",
                "data": {"filename": filename, "filepath": str(filepath)}
            })
            
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Dashboard PDF report failed: {e}")
            await manager.send_to_user(user_id, {
                "type": "export_error",
                "title": "대시보드 리포트 생성 실패",
                "message": f"리포트 생성 중 오류가 발생했습니다: {str(e)}",
                "severity": "error"
            })
            raise
    
    async def generate_purchase_request_document(
        self,
        purchase_request: PurchaseRequest,
        requester: User,
        approver: User
    ) -> str:
        """구매요청 지출품의서 PDF 생성"""
        try:
            # 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"purchase_request_{purchase_request.id}_{timestamp}.pdf"
            filepath = self.export_dir / filename

            # PDF 문서 생성
            doc = SimpleDocTemplate(str(filepath), pagesize=A4)
            story = []

            # 제목
            title = Paragraph("지출품의서", self.title_style)
            story.append(title)
            story.append(Spacer(1, 20))

            # 문서 번호 및 생성 정보
            doc_info = Paragraph(
                f"문서번호: PR-{purchase_request.id:05d}<br/>"
                f"생성일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')}",
                self.normal_style
            )
            story.append(doc_info)
            story.append(Spacer(1, 30))

            # 기본 정보
            basic_info_heading = Paragraph("기본 정보", self.heading_style)
            story.append(basic_info_heading)

            basic_info_data = [
                ['구분', '내용'],
                ['제목', purchase_request.title],
                ['설명', purchase_request.description or '-'],
                ['요청자', requester.name if requester else '-'],
                ['요청자 이메일', requester.email if requester else '-'],
                ['승인자', approver.name if approver else '-'],
                ['승인일시', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                ['상태', '승인됨']
            ]

            basic_info_table = Table(basic_info_data, colWidths=[2*inch, 4*inch])
            basic_info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), self.korean_font),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            story.append(basic_info_table)
            story.append(Spacer(1, 30))

            # 지출 상세 정보
            expense_heading = Paragraph("지출 상세", self.heading_style)
            story.append(expense_heading)

            expense_data = [
                ['항목', '내용'],
                ['지출 카테고리', purchase_request.resource_type or '-'],
                ['공급업체', purchase_request.vendor or '-'],
                ['수량', str(purchase_request.quantity) if purchase_request.quantity else '-'],
                ['금액', f"{purchase_request.amount:,.0f}원" if purchase_request.amount else '-'],
                ['우선순위', purchase_request.priority or '-'],
                ['희망 완료일', purchase_request.due_date.strftime('%Y-%m-%d') if purchase_request.due_date else '-']
            ]

            expense_table = Table(expense_data, colWidths=[2*inch, 4*inch])
            expense_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), self.korean_font),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            story.append(expense_table)
            story.append(Spacer(1, 30))

            # 총액 표시
            if purchase_request.amount:
                total_amount = Paragraph(
                    f"<b>총 지출 금액: {purchase_request.amount:,.0f}원</b>",
                    self.heading_style
                )
                story.append(total_amount)
                story.append(Spacer(1, 20))

            # 승인자 코멘트 (있는 경우)
            if purchase_request.approver_comment:
                comment_heading = Paragraph("승인자 의견", self.heading_style)
                story.append(comment_heading)

                comment_para = Paragraph(purchase_request.approver_comment, self.normal_style)
                story.append(comment_para)
                story.append(Spacer(1, 30))

            # 서명란
            signature_heading = Paragraph("서명", self.heading_style)
            story.append(signature_heading)

            signature_data = [
                ['요청자', '승인자'],
                [f"{requester.name}\n_____________", f"{approver.name}\n_____________"]
            ]

            signature_table = Table(signature_data, colWidths=[3*inch, 3*inch])
            signature_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), self.korean_font),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 20),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
            ]))

            story.append(signature_table)
            story.append(Spacer(1, 30))

            # 문서 하단 정보
            footer_style = ParagraphStyle(
                'Footer',
                parent=self.normal_style,
                fontSize=8,
                textColor=colors.grey
            )
            footer_text = Paragraph(
                "본 문서는 BrandFlow 시스템에서 자동 생성되었습니다.",
                footer_style
            )
            story.append(footer_text)

            # PDF 빌드
            doc.build(story)

            logger.info(f"Purchase request document generated: {filename}")

            return str(filepath)

        except Exception as e:
            logger.error(f"Purchase request document generation failed: {e}")
            raise

    async def cleanup_old_exports(self, days: int = 7):
        """오래된 내보내기 파일 정리"""
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        deleted_count = 0

        for file_path in self.export_dir.rglob('*'):
            if file_path.is_file():
                try:
                    if file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()
                        deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete old export file {file_path}: {e}")

        logger.info(f"Cleaned up {deleted_count} old export files")
        return deleted_count

# 전역 내보내기 서비스 인스턴스
export_service = ExportService()