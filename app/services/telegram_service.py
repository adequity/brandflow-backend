import asyncio
import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)


class TelegramService:
    """텔레그램 봇 API 서비스"""

    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.timeout = 30.0

    async def send_message(
        self,
        chat_id: str,
        message: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True
    ) -> Dict[str, Any]:
        """텔레그램 메시지 전송"""

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")

        url = f"{self.base_url}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        logger.info(f"텔레그램 메시지 전송 성공: chat_id={chat_id}")
                        return {
                            "success": True,
                            "message_id": result.get("result", {}).get("message_id"),
                            "data": result
                        }
                    else:
                        error_msg = result.get("description", "알 수 없는 오류")
                        logger.error(f"텔레그램 API 오류: {error_msg}")
                        return {
                            "success": False,
                            "error": error_msg,
                            "error_code": result.get("error_code")
                        }
                else:
                    logger.error(f"텔레그램 API HTTP 오류: {response.status_code}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "error_code": response.status_code
                    }

        except httpx.TimeoutException:
            logger.error("텔레그램 API 타임아웃")
            return {
                "success": False,
                "error": "요청 타임아웃",
                "error_code": "TIMEOUT"
            }
        except Exception as e:
            logger.error(f"텔레그램 메시지 전송 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "UNKNOWN"
            }

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """채팅 정보 조회 (chat_id 유효성 검증용)"""

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")

        url = f"{self.base_url}/getChat"
        payload = {"chat_id": chat_id}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        return {
                            "success": True,
                            "data": result.get("result", {})
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("description", "알 수 없는 오류")
                        }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"텔레그램 채팅 정보 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def send_campaign_deadline_reminder(
        self,
        chat_id: str,
        user_name: str,
        post_title: str,
        due_date: str,
        days_left: int,
        campaign_id: int,
        post_id: int
    ) -> Dict[str, Any]:
        """캠페인 마감일 알림 메시지 전송"""

        # 마감일이 임박한 정도에 따른 이모지 선택
        if days_left <= 1:
            urgency_emoji = "🚨"
            urgency_text = "긴급"
        elif days_left <= 2:
            urgency_emoji = "⚠️"
            urgency_text = "중요"
        else:
            urgency_emoji = "📅"
            urgency_text = "알림"

        message = f"""
{urgency_emoji} <b>{urgency_text} - 캠페인 마감일 알림</b>

안녕하세요, <b>{user_name}</b>님!

📝 <b>작업명:</b> {post_title}
📅 <b>마감일:</b> {due_date}
⏰ <b>남은 시간:</b> <b>{days_left}일</b>

🔗 <b>캠페인 ID:</b> {campaign_id}
📋 <b>작업 ID:</b> {post_id}

마감일이 다가오고 있습니다. 작업 진행 상황을 확인해 주세요!

<i>BrandFlow 알림 시스템</i>
        """.strip()

        return await self.send_message(chat_id, message)

    async def send_test_message(self, chat_id: str, user_name: str) -> Dict[str, Any]:
        """테스트 메시지 전송"""

        message = f"""
🤖 <b>텔레그램 알림 테스트</b>

안녕하세요, <b>{user_name}</b>님!

✅ 텔레그램 알림이 정상적으로 설정되었습니다.
📱 이제 캠페인 마감일 알림을 받으실 수 있습니다.

<b>알림 설정:</b>
• 마감일 2일 전 알림
• 매일 오전 9시 발송

설정을 변경하시려면 시스템 설정에서 수정해 주세요.

<i>BrandFlow 알림 시스템</i>
        """.strip()

        return await self.send_message(chat_id, message)


# 전역 텔레그램 서비스 인스턴스
telegram_service = TelegramService()


async def send_telegram_message(chat_id: str, message: str) -> Dict[str, Any]:
    """간편한 텔레그램 메시지 전송 함수"""
    return await telegram_service.send_message(chat_id, message)


async def validate_telegram_chat_id(chat_id: str) -> bool:
    """텔레그램 채팅 ID 유효성 검증"""
    try:
        result = await telegram_service.get_chat_info(chat_id)
        return result.get("success", False)
    except Exception:
        return False