## 1. 솔루션 한 줄 요약 (One-line Summary)

**일상 속 접근성 정보를 AI로 자동 판별하여 제공하는 사용자 참여형 배리어프리맵**

**A crowdsourced barrier-free map that automatically identifies accessibility information using AI.**

## 2. 풀고자 하는 사회 문제 정의 (Problem Definition)

### **"정보의 부재가 물리적 장애만큼 큰 장벽입니다."**

### **"Absence of information is as big a barrier as physical disability."**

- **접근성 정보 확인의 어려움**: 휠체어 사용자의 70%가 목적지에 경사로 등이 있는지 확인하는 데 어려움을 겪고 있습니다.
- **정보의 부재**: 지도나 리뷰 플랫폼에 등록된 장소 중 60%는 접근 가능 여부에 대한 정보조차 없습니다.
- **기존 서비스의 한계**:
    - **지속성 부족**: 초기 데이터 구축 후 업데이트가 되지 않아 정보의 신뢰도가 낮습니다.
    - **데이터 파편화**: 정보가 여러 곳에 흩어져 있어 통합적인 확인이 어렵습니다.
    - **지역 편중**: 서울 및 수도권에 데이터가 집중되어 있습니다.
- **Difficulty in checking accessibility**: 70% of wheelchair users find it difficult to check if a destination has ramps or stairs.
- **Absence of Information**: 60% of places on maps or review platforms lack even basic accessibility information.
- **Limitations of Existing Services**:
    - **Lack of Sustainability**: Information reliability drops due to a lack of updates after initial data construction.
    - **Data Fragmentation**: Information is scattered, making integrated verification difficult.
    - **Regional Bias**: Data is concentrated in Seoul and metropolitan areas.

## 3. 솔루션 개요 (Solution Overview)

### **휠도시의 핵심 기능 (Key Features)**

1. **간편한 데이터 수집 (Simple Data Collection)**: 사용자 참여(Crowdsourcing)를 통해 장소와 이미지 입력을 최대한 간단하게 만듭니다.
2. **AI 기반 자동 판별 (AI-based Automatic Detection)**: **YOLOv8**과 **Gemini**를 활용한 2-step 모델로 입구 사진만으로 접근성 정보(경사로 유무, 문턱 등)를 표준화된 태그로 자동 생성합니다.
3. **신뢰도 강화 루프 (Reliability Loop)**: 지도 시각화 및 사용자 피드백을 통해 데이터가 지속적으로 업데이트되고 정교해지는 선순환 구조를 만듭니다.

### **기대 효과 및 차별점 (Expected Effects & Differentiation)**

- **지속적인 최신화**: 관리 미흡으로 방치되는 기존 지도와 달리, 사용자 참여와 AI 자동화를 통해 정보를 최신 상태로 유지합니다.
- **방대한 데이터 커버리지**: 자동화된 검증을 통해 특정 지역에 국한되지 않고 일반 지도 서비스 수준의 넓은 커버리지를 목표로 합니다.
- **개인 맞춤형 정보**: 사용자의 휠체어 스펙을 고려하여 개인별 접근 가능 여부를 제공합니다.

### **Differentiation**

- **Continuous Updates**: Unlike existing static maps, we maintain up-to-date information through user participation and AI automation.
- **Massive Data Coverage**: We aim for broad coverage comparable to general map services through automated verification.
- **Personalized Information**: We provide accessibility details tailored to individual wheelchair specifications.

## 4. 설치 및 실행 방법 (Installation & Usage)

이 프로젝트는 Frontend와 Backend 리포지토리로 구성되어 있습니다. 상세한 설치 및 실행 방법은 각 리포지토리를 참고해 주세요.
This project consists of Frontend and Backend repositories. Please refer to each repository for detailed installation and execution instructions.

### **Frontend (HTML / Javascript / CSS)**

- **Repository**: https://github.com/lollipop719/WheelCity_front_2025

```
git clone https://github.com/lollipop719/WheelCity_front_2025
cd WheelCity_front_2025
npm install
npm start

```

### **Backend (Python / FastAPI)**

- **Repository**: https://github.com/kang022878/WheelCity_back_2025
- **AI Models**: YOLOv8, Gemini API
- **Database**: MongoDB, AWS S3

```
git clone https://github.com/kang022878/wheel_city_server
cd wheel_city_server
pip install -r requirements.txt
uvicorn main:app --reload

```

### **AI (YOLOv8, Gemini API)**

- **Repository**: https://github.com/AsyncNomad/WheelCity_AI_2025

## 5. 데모 영상 (Demo Video)

https://drive.google.com/file/d/1FDLIXpQlXcAVRUNkvkp9R28v2NBAAoga/view?usp=sharing

## 6. 연관 자료 (References)

- **협동조합 무의 (Cooperative Muui)**: [프로젝트 협력 파트너 (Project Partner)](https://www.wearemuui.com/)
- **관련 기술 (Tech Stack)**: YOLOv8, Gemini API, React Native, FastAPI, MongoDB

## 7. 팀 및 팀원 소개 (Team Introduction)

- **Team 휠도시 (WheelCity)**는 KAIST CS499 <테크 포 임팩트> 수업의 일환으로, 기술을 통해 이동약자의 정보 불평등 문제를 해결하고자 합니다.

### **Members**

- **고은서 (Ko Eunseo)**: PM (Project Manager)
- **권정준 (Gwon Jeongjoon)**: UI/UX, Front-end Developer
- **이상범 (Lee Sangbum)**: AI Engineer, Front-end Developer
- **황지훈 (Hwang Jihoon)**: Full Stack Developer
- **강서현 (Kang Seohyun)**: Back-end Developer

### **Partners**

- **협동조합 무의 (Cooperative Muui)**: 멘토링 및 필드 데이터 지원 (Mentoring & Field Data Support)
- **카카오 멘토 김성민 (Kakao Mentor Kris):** 기술 멘토링

### **Contact (Github / Email)**

- 고은서: @esgogo02 / esgogo@kaist.ac.kr
- 권정준: @gwonjeongjoon / jgwon7436@kaist.ac.kr
- 이상범: @AsyncNomad / sangddung2@kaist.ac.kr
- 황지훈: @lollipop719 / jihwang@kaist.ac.kr
- 강서현: @kang022878 / kang022878@kaist.ac.kr


