#!/bin/bash
# 더블클릭하면 서버를 시작하고 창을 유지한다
cd "$(dirname "$0")"
./server.sh start
echo ""
echo "이 창을 닫아도 서버는 계속 실행됩니다. (종료: ./server.sh stop 또는 서버종료.command)"
exec bash --noprofile -i
