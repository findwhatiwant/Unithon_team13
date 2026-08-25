#!/bin/bash
# Magic Note 시연 서버 관리 스크립트
# 사용법: ./server.sh {start|stop|restart|status|logs}

set -uo pipefail
cd "$(dirname "$0")"

PORT=8000
VENV=".venv"
PID_FILE="/tmp/magicnote-server.pid"
LOG_FILE="/tmp/magicnote-server.log"

is_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

ensure_env() {
    # 가상환경 없으면 생성 + 의존성 설치
    if [ ! -d "$VENV" ]; then
        echo "📦 가상환경 생성 중..."
        python3 -m venv "$VENV"
        "$VENV/bin/pip" install -q -e ".[dev]" fastapi "uvicorn" 2>&1 | tail -1
    fi
    # 필수 패키지 확인
    if ! "$VENV/bin/python" -c "import fastapi, uvicorn" 2>/dev/null; then
        echo "📦 의존성 설치 중..."
        "$VENV/bin/pip" install -q -e ".[dev]" fastapi "uvicorn"
    fi
    # .env 확인
    if [ ! -f ".env" ]; then
        echo "⚠️  .env 파일이 없습니다! GEMINI_API_KEY와 SUPABASE_URL/KEY를 설정하세요."
        exit 1
    fi
}

cmd_start() {
    if is_running; then
        echo "✅ 서버가 이미 실행 중입니다 (포트 $PORT)"
        exit 0
    fi
    ensure_env

    # 포트 점유 확인 (다른 프로세스가 쓰고 있으면 종료)
    if lsof -ti ":$PORT" >/dev/null 2>&1; then
        echo "🔄 포트 $PORT 점유 프로세스 종료 중..."
        lsof -ti ":$PORT" | xargs kill -9 2>/dev/null
        sleep 1
    fi

    echo "🚀 서버 시작 중... (http://127.0.0.1:$PORT)"
    nohup "$VENV/bin/python" -m uvicorn refiner.server:app --host 127.0.0.1 --port "$PORT" \
        > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    # 헬스체크 (최대 10초 대기)
    for i in $(seq 1 20); do
        if curl -s "http://127.0.0.1:$PORT/health" | grep -q '"ok":true'; then
            echo ""
            echo "✅ 서버 준비 완료!"
            echo "   주소: http://127.0.0.1:$PORT"
            echo "   상태: $(curl -s http://127.0.0.1:$PORT/health)"
            echo "   로그: tail -f $LOG_FILE"
            exit 0
        fi
        sleep 0.5
    done

    echo "❌ 서버 시작 실패. 로그 확인:"
    tail -20 "$LOG_FILE"
    exit 1
}

cmd_stop() {
    if is_running; then
        kill "$(cat "$PID_FILE")" 2>/dev/null
        rm -f "$PID_FILE"
        echo "🛑 서버를 종료했습니다."
    else
        # PID 파일 없어도 포트에 살아있으면 정리
        if lsof -ti ":$PORT" >/dev/null 2>&1; then
            lsof -ti ":$PORT" | xargs kill 2>/dev/null
            echo "🛑 포트 $PORT의 프로세스를 종료했습니다."
        else
            echo "서버가 실행 중이 아닙니다."
        fi
    fi
}

cmd_status() {
    if is_running || lsof -ti ":$PORT" >/dev/null 2>&1; then
        echo "● 실행 중 (포트 $PORT)"
        curl -s "http://127.0.0.1:$PORT/health" && echo ""
    else
        echo "○ 중지됨"
    fi
}

case "${1:-}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_stop; sleep 1; cmd_start ;;
    status)  cmd_status ;;
    logs)    tail -f "${LOG_FILE}" ;;
    *)       echo "사용법: ./server.sh {start|stop|restart|status|logs}" ;;
esac
