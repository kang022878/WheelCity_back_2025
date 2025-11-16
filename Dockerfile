# 1. Python 베이스 이미지
FROM python:3.11-slim

# 2. 시스템 패키지 설치 (YOLOv8, torch, opencv 동작용)
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리
WORKDIR /app

# 4. Python dependency 복사 & 설치
COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. 전체 코드 복사
COPY . .

# 6. FastAPI 실행 포트 설정
ENV PORT=8000

# 7. FastAPI 실행 명령
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
