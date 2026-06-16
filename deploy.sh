#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  deploy.sh  ─  단 하나의 명령으로 최신화 → 빌드 → 푸시 → 실행
#
#  사용법 (레포 클론 후 EC2 에서 실행):
#    bash deploy.sh
#
#  이 스크립트는 다음을 자동으로 수행합니다:
#    1. Docker 미설치 시 자동 설치 (Ubuntu / Amazon Linux 2)
#    2. GitHub 최신 코드 강제 동기화
#    3. Docker 캐시/이미지 정리로 디스크 공간 확보
#    4. DockerHub 로그인
#    5. 백엔드 / 프론트엔드 이미지 빌드 (docker compose)
#    6. 두 이미지 DockerHub 푸시
#    7. 기존 컨테이너 및 볼륨 완전 삭제
#    8. docker compose up (db + back + front)
#    9. 접속 URL 안내
# ─────────────────────────────────────────────────────────────────

set -euo pipefail

DOCKER_USER="yooahreaum"

GREEN="\033[0;32m"; YELLOW="\033[1;33m"; CYAN="\033[0;36m"; RESET="\033[0m"
info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 국내 여행지 추천 서비스 — 빌드 & 배포 스크립트"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── [Step 1] Docker 설치 확인 및 자동 설치 ──────────────────────
if ! command -v docker &>/dev/null; then
    warn "Docker 가 설치되어 있지 않습니다. 자동 설치를 시작합니다..."

    if command -v apt-get &>/dev/null; then
        info "Ubuntu/Debian 환경 감지 → Docker 설치 중..."
        sudo apt-get update -y -qq
        sudo apt-get install -y -qq ca-certificates curl gnupg lsb-release
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) \
signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
            | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo apt-get update -y -qq
        sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker "$USER" 2>/dev/null || true

    elif command -v yum &>/dev/null; then
        info "Amazon Linux/RHEL 환경 감지 → Docker 설치 중..."
        sudo yum update -y -q
        sudo yum install -y -q docker
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker "$USER" 2>/dev/null || true
    else
        echo "지원하지 않는 OS 입니다. Docker 를 수동으로 설치하세요."
        echo "  https://docs.docker.com/engine/install/"
        exit 1
    fi

    success "Docker 설치 완료."
    warn "그룹 권한 적용을 위해 스크립트를 다시 실행해 주세요:"
    echo "  bash deploy.sh"
    exit 0
fi

success "Docker $(docker --version | awk '{print $3}' | tr -d ',') 확인"

# ── [Step 2] GitHub 최신 코드 강제 동기화 ───────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "[Step 2] GitHub 최신 코드 강제 동기화"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v git &>/dev/null && [ -d ".git" ]; then
    git fetch origin
    git reset --hard origin/main
    success "origin/main 기준으로 강제 동기화 완료"
else
    warn "git 저장소가 아니거나 git 미설치 — 코드 동기화 건너뜀"
fi

# ── [Step 3] Docker 캐시 정리 (디스크 공간 확보) ────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "[Step 3] 미사용 Docker 리소스 정리"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker system prune -f
success "Docker 캐시 정리 완료"

# ── [Step 4] DockerHub 로그인 ────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "[Step 4] DockerHub 로그인 (${DOCKER_USER})"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker login
success "DockerHub 로그인 완료"

# ── [Step 5] 이미지 빌드 ─────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "[Step 5] 백엔드 / 프론트엔드 이미지 빌드"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose build
success "이미지 빌드 완료"

# ── [Step 6] DockerHub 푸시 ──────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "[Step 6] 이미지 DockerHub 푸시"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose push
success "DockerHub 푸시 완료"

# ── [Step 7] 기존 컨테이너 및 볼륨 완전 삭제 ────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "[Step 7] 기존 컨테이너 및 볼륨 삭제"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose down -v 2>/dev/null && success "기존 컨테이너/볼륨 삭제 완료" || true

# ── [Step 8] 서비스 시작 ─────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "[Step 8] 서비스 시작 (db + back + front)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose up -d
success "모든 서비스 시작 완료"

echo ""
info "컨테이너 상태 확인 중..."
sleep 3
docker compose ps

# ── [Step 9] 접속 URL 출력 ───────────────────────────────────────
PUBLIC_IP=$(curl -s --max-time 3 \
    http://169.254.169.254/latest/meta-data/public-ipv4 \
    2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN} 배포 완료!${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "  Streamlit (프론트)  →  ${CYAN}http://${PUBLIC_IP}:8501${RESET}"
echo -e "  FastAPI   (백엔드)  →  ${CYAN}http://${PUBLIC_IP}:8000/docs${RESET}"
echo ""
echo " 유용한 명령어:"
echo "   docker compose ps                  # 컨테이너 상태"
echo "   docker compose logs -f             # 전체 실시간 로그"
echo "   docker compose logs -f back        # 백엔드 로그"
echo "   docker compose down                # 서비스 중지"
echo "   docker compose down -v             # 서비스 중지 + 볼륨 삭제"
echo ""
echo " DockerHub 이미지:"
echo "   ${DOCKER_USER}/travel-back:latest"
echo "   ${DOCKER_USER}/travel-front:latest"
echo ""
echo " EC2 보안그룹 인바운드 허용 확인:"
echo "   포트 8501 (Streamlit) / 8000 (FastAPI)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
