# PUAD: PatchCore Unsupervised Anomaly Detection

> **Automated Optical Inspection (AOI) System for Precision Electronic Components**  
> Real-Time Visual Defect Detection & Localization with Zero Defect Training Data.

---

## 1. Overview

PUAD(PatchCore Unsupervised Anomaly Detection)는 제조 공정에서 정상(Normal) 부품 데이터만을 학습하여 미세 결함(스크래치, 핀 휨, 과열/소손, 이물 오염, 단자 누락 등)을 실시간으로 검출하고 국소화(Localization)하는 산업용 스마트 머신비전 검사 시스템입니다.

지도학습 기반 검사 시스템과 달리 불량 샘플 수집 및 라벨링 비용이 들지 않으며, 소량의 정상 샘플(10~15장) 등록만으로 현장에서 수 초 내에 최적의 결함 판정 모델을 배포할 수 있습니다.

---

## 2. Key Architecture & Features

### 2.1 PatchCore Algorithm & Feature Bank
- **Backbone Architecture**: 사전 학습된 `ResNet-18` 백본의 중간 레이어(Layer 2, Layer 3)에서 고차원 패치 임베딩을 추출하여 국소 특징과 문맥 정보를 동시에 확보합니다.
- **Coreset Subsampling**: 수만 개의 패치 벡터 중 기하학적 다양성을 보존하는 핵심 패치만을 선별(Coreset Subsampling)하여 메모리 풋프린트를 대폭 절감하고 실시간 추론 속도를 보장합니다.
- **Explainable Heatmap**: 결함 판정 점수(Anomaly Score) 산출과 동시에 원본 이미지 대비 이상 부위를 픽셀 단위 히트맵으로 오버레이하여 결함 원인 분석을 지원합니다.
- **Hardware Acceleration**: Apple Silicon MPS(Metal Performance Shaders) 및 CUDA, CPU 가속을 지원하여 15~30 FPS (~15ms)의 저지연 실시간 검사가 가능합니다.

### 2.2 Commercial Web Inspection Dashboard
- **Zero-Delay 3-Screen Layout**: 메인 광학 뷰포트(LIVE)와 서브 검사창(ROI, HEATMAP)을 네이티브 CSS Grid로 구성하여 비디오 소켓 재연결 없이 0ms로 화면 전환을 수행합니다.
- **Dynamic Inspection Zone (ROI)**: 부품 크기와 카메라 거리에 맞추어 검사 영역 크기(140px ~ 480px)를 실시간으로 미세 조정할 수 있습니다.
- **Dual Laboratory Themes**: 고대비 클린룸 환경을 위한 고신뢰도 라이트 모드(Light Theme)와 인더스트리얼 다크 모드(Dark Theme)를 원클릭으로 전환할 수 있습니다.
- **Camera & Hardware Power Management**: 하단 제어 레일을 통해 광학 센서 하드웨어를 즉시 대기(Standby) 및 완전 릴리즈하여 전력 소모 및 발열을 제어할 수 있습니다.
- **Continuity Camera & Multi-Device Support**: Mac 내장 웹캠, USB 공업용 카메라, iPhone 연속성 카메라 및 네트워크 IP 스트림을 실시간 선택하여 전환할 수 있습니다.

### 2.3 Hardware & PLC Integration
- **Serial Communication Bridge**: 아두이노 기반 컨베이어 및 분류 시스템과 USB 시리얼(115200 Baud)로 통신합니다.
- **Optical Trigger**: 적외선(IR) 근접 센서의 `TRIGGER` 신호 수신 즉시 판정을 수행합니다.
- **Automated Sorting**: 판정 결과(`PASS` / `FAIL`)를 액추에이터(서보모터/솔레노이드 밸브)로 전달하여 양품과 불량품을 자동 분별 배출합니다.
- **Simulation Fallback**: 물리 장비가 연결되지 않은 경우 소프트웨어 시뮬레이션 모드로 자동 전환됩니다.

---

## 3. Directory Structure

```
PUAD/
├── server.py                   # FastAPI 기반 실시간 웹 AOI 서버 & WebSocket 엔진
├── main.py                     # OpenCV 데스크톱 독립형 HUD 검사 창
├── requirements.txt            # Python 의존성 라이브러리 목록
├── .gitignore                  # Git 버전 관리 예외 규칙
├── README.md                   # 프로젝트 기술 명세서
│
├── model/                      # PatchCore AI 파이프라인
│   ├── feature_extractor.py    # ResNet-18 패치 임베딩 추출기
│   └── patchcore.py            # 코어셋 서브샘플링 및 거리 기반 이상치 탐지 엔진
│
├── utils/                      # 하드웨어 및 보조 유틸리티
│   ├── camera.py               # 스레드 안전(RLock) 카메라 제어 및 ROI 추출기
│   ├── detector.py             # 부품 유무(Presence) 및 윤곽선 분석기
│   ├── visualizer.py           # 데스크톱 HUD 시각화 모듈
│   └── sound.py                # 시스템 오디오 신호 제어
│
├── web/                        # 상업용 대시보드 웹 인터페이스
│   ├── templates/
│   │   └── index.html          # 메인 AOI 모니터링 대시보드 템플릿
│   └── static/
│       ├── css/style.css       # 산업용 고대비 디자인 시스템 (라이트/다크 모드)
│       └── js/app.js           # 0ms 스트림 전환, 텔레메트리 및 하드웨어 연동 컨트롤러
│
├── arduino/                    # PLC / 임베디드 펌웨어 및 브릿지
│   ├── conveyor_controller.ino # 컨베이어 모터 및 서보 분류기 펌웨어
│   └── arduino_bridge.py       # 시리얼 통신 브릿지 (자동 포트 탐색)
│
└── data/
    ├── models/                 # 배포된 PatchCore 가중치 및 메모리 뱅크 (.pkl)
    └── normal/                 # 정상 기준 샘플 데이터셋 (.png)
```

---

## 4. Installation & Environment

### Requirements
- Python 3.9 이상
- PyTorch 2.0 이상 (macOS MPS 또는 CUDA 권장)
- OpenCV (cv2)
- FastAPI & Uvicorn

### Setup

```bash
# 1. 저장소 클론
git clone https://github.com/corkcicle123/PUAD.git
cd PUAD

# 2. 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 3. 의존성 패키지 설치
pip install -r requirements.txt
```

---

## 5. Execution Guide

### Option 1: Web AOI Dashboard (Recommended)

웹 기반 통합 관제 인터페이스를 실행합니다:

```bash
python3 server.py --port 8000
```

- **접속 주소**: `http://localhost:8000`
- **주요 인터페이스 기능**:
  - `[CH-01 LIVE]`, `[CH-02 ROI]`, `[CH-03 HEATMAP]` 3분할 화면 및 메인 확대 전환
  - 인스펙션 존 크기 슬라이더 (140px ~ 480px 및 200/280/380px 프리셋)
  - 불량 판정 임계치(Threshold) 미세 조절
  - 라이트/다크 테마 토글 버튼 (`☀️` / `🌙`)
  - 카메라 끄기 및 검사 일시중지 버튼 (`⏸️` / `▶️`)
  - 실시간 SPC 통계 (총 검사 수, 수율, 불량률, 추론 지연 시간, 감사 로그)

### Option 2: Desktop Native HUD

브라우저 없이 OpenCV 고해상도 그래픽 창으로 직접 실행합니다:

```bash
python3 main.py
```

- **키보드 단축키**:
  - `C`: 정상 부품 샘플 캡처 등록
  - `T`: 수집된 샘플 기반 모델 학습 및 배포
  - `SPACE`: 단일 샷 수동 검사
  - `R`: 샘플 데이터 및 통계 초기화
  - `+` / `-`: 판정 임계치(Threshold) 조절
  - `Q` / `ESC`: 프로그램 종료

---

## 6. Hardware Integration Protocol

### 6.1 Serial Specifications
- **Baud Rate**: `115200`
- **Data Bits**: 8
- **Parity**: None
- **Stop Bits**: 1

### 6.2 Communication Frame
| 방향 | 메시지 | 설명 |
|:---|:---|:---|
| Arduino → Host PC | `TRIGGER\n` | IR 센서 부품 감지 신호 |
| Arduino → Host PC | `ARDUINO_READY\n` | 컨트롤러 부팅 및 준비 완료 |
| Host PC → Arduino | `PASS\n` | 양품 판정 (컨베이어 연속 통과) |
| Host PC → Arduino | `FAIL\n` | 불량 판정 (서보/솔레노이드 배출 구동) |

---

## 7. License

본 프로젝트는 연구 및 산업용 프로토타입 용도로 제작되었습니다.
