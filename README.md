🏙️ Wheel City Server

FastAPI + MongoDB 기반의 휠도시 접근성 데이터 백엔드 서버입니다.
가게의 입구 접근성(경사로/계단/자동문 등)을 저장하고, 프런트엔드 지도와 연동할 수 있도록 API를 제공합니다.

📋 요구사항
1. Python 3.9+
2. 가상환경 (venv)
3. MongoDB Atlas 계정 및 클러스터
4. VS Code (권장)

🚀 시작하기
## 1. 저장소 클론 & 환경 준비
git clone <this-repo-url> wheel_city_server
cd wheel_city_server

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

## 2. 환경 변수 설정
프로젝트 루트에 .env 파일 생성:

MONGO_URI=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/
DB_NAME=wheel_city

API_KEY_INTERNAL=dev-secret-key

CORS_ORIGINS=http://127.0.0.1:5500,http://localhost:5500

## 3. MongoDB Atlas 설정
3.1. Atlas에서 클러스터 생성 (무료 M0 가능)
3.2. Database User 생성 (username / password)
3.3. Network Access → 0.0.0.0/0 추가 (개발용)
3.4. Clusters → Connect → Connect your application → Python 드라이버 선택 → Connection String 복사
3.5. .env 의 MONGO_URI 값에 붙여넣기

## 4. 프로젝트 구조
wheel_city_server/
├── app/
│   ├── main.py              # FastAPI 진입점
│   ├── db.py                # MongoDB 연결
│   ├── models.py            # 데이터 직렬화/스키마
│   ├── deps.py              # 의존성 주입
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py        # 헬스체크 API (/health)
│   │   ├── places.py        # 장소 관련 API (/places)
│   │   └── reports.py       # 사용자 제보 API (/reports)
│   └── services/
│       ├── aggregation.py   # 통계/집계 로직
│       └── inference_bridge.py # ML 결과 연동
├── scripts/
│   ├── create_indexes.py    # DB 인덱스 생성 스크립트
│   └── seed_data.py         # 샘플 데이터 넣기
├── requirements.txt
├── .env.example
└── README.md

## 5. 서버 실행
uvicorn app.main:app --reload

서버 실행 후 브라우저에서 확인:
http://127.0.0.1:8000/docs → Swagger UI
http://127.0.0.1:8000/health → 헬스체크

## 6. 예시 API

GET /health → 서버 상태 확인

GET /places/nearby?lat=37.5663&lng=126.9779&radius=1000
→ 특정 위치 주변의 접근성 장소 데이터 반환

POST /reports/{place_id}
→ 사용자 제보 등록

🛠️ 개발 편의
1. 인덱스 생성
python scripts/create_indexes.py

2. 샘플 데이터 삽입
python scripts/seed_data.py

🔒 보안 주의사항
.env 파일은 절대 GitHub에 올리지 말 것
MongoDB Atlas User 비밀번호는 강력하게 설정
배포 시에는 0.0.0.0/0 대신 서버 IP만 화이트리스트로 설정

📌 TODO
 AI 추론 결과 저장 엔드포인트 구현 (inference_bridge.py)
 사용자 제보 검증 프로세스 추가
 지도 프런트엔드와 API 연동
 
