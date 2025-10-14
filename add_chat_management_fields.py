"""
카톡 관리 필드 추가 마이그레이션 스크립트
Campaign 테이블에 chat_content, chat_summary, chat_attachments, chat_images 필드 추가
"""
import os
import sys
from sqlalchemy import create_engine, text, MetaData, Table, Column, Text, inspect

# 환경 변수에서 데이터베이스 URL 가져오기
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:eCLUGwjuJMbfPHyaWHFRhEJXQFgAKEKE@autorack.proxy.rlwy.net:28902/railway"
)

def add_chat_management_fields():
    """Campaign 테이블에 카톡 관리 필드 추가"""
    engine = create_engine(DATABASE_URL)

    try:
        with engine.connect() as conn:
            # 트랜잭션 시작
            trans = conn.begin()

            try:
                # Inspector로 현재 테이블 구조 확인
                inspector = inspect(engine)
                existing_columns = [col['name'] for col in inspector.get_columns('campaigns')]

                print("현재 campaigns 테이블 컬럼:", existing_columns)

                # 추가할 필드 목록
                fields_to_add = [
                    ('chat_content', 'TEXT'),
                    ('chat_summary', 'TEXT'),
                    ('chat_attachments', 'TEXT'),
                    ('chat_images', 'TEXT')
                ]

                added_fields = []

                for field_name, field_type in fields_to_add:
                    if field_name not in existing_columns:
                        sql = text(f"""
                            ALTER TABLE campaigns
                            ADD COLUMN {field_name} {field_type}
                        """)
                        conn.execute(sql)
                        added_fields.append(field_name)
                        print(f"✅ {field_name} 필드 추가 완료")
                    else:
                        print(f"⏭️  {field_name} 필드는 이미 존재합니다")

                # 트랜잭션 커밋
                trans.commit()

                if added_fields:
                    print(f"\n🎉 마이그레이션 성공! 추가된 필드: {', '.join(added_fields)}")
                else:
                    print("\n✨ 모든 필드가 이미 존재합니다. 마이그레이션 불필요")

                # 최종 테이블 구조 확인
                inspector = inspect(engine)
                final_columns = [col['name'] for col in inspector.get_columns('campaigns')]
                print(f"\n최종 campaigns 테이블 컬럼: {final_columns}")

                return True

            except Exception as e:
                trans.rollback()
                print(f"❌ 마이그레이션 실패: {e}")
                return False

    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return False
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("=" * 60)
    print("카톡 관리 필드 마이그레이션 시작")
    print("=" * 60)

    success = add_chat_management_fields()

    if success:
        sys.exit(0)
    else:
        sys.exit(1)
