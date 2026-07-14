#!/bin/bash
# XH-202621 一键启动脚本 (Git Bash / Linux / Mac)
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m'

# 1. 停掉旧进程
echo -e "${CYAN}==> 停止已有服务...${NC}"
for port in 8080 8501; do
  pid=$(netstat -ano 2>/dev/null | grep ":$port " | grep LISTENING | awk '{print $5}' | head -1) || true
  if [ -n "$pid" ]; then
    taskkill //F //PID "$pid" 2>/dev/null || true
    echo -e "${GRAY}    已停止 PID $pid (端口 $port)${NC}"
  fi
done

# 2. 编译后端
echo -e "${CYAN}==> 编译 Java 后端...${NC}"
javac -encoding UTF-8 -d backend/out backend/src/com/xh202621/*.java
echo -e "${GREEN}    编译成功${NC}"

# 3. 启动后端
echo -e "${CYAN}==> 启动后端 (http://localhost:8080)...${NC}"
java -cp backend/out com.xh202621.App &
BACKEND_PID=$!
echo -e "${GREEN}    后端 PID: $BACKEND_PID${NC}"

# 4. 等后端就绪
echo -e "${CYAN}==> 等待后端就绪...${NC}"
for i in $(seq 1 30); do
  if curl -s http://localhost:8080/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}    后端已就绪${NC}"
    break
  fi
  sleep 0.5
done

# 5. 启动前端
echo -e "${CYAN}==> 启动前端 (http://localhost:8501)...${NC}"
python frontend/app.py &
FRONTEND_PID=$!
echo -e "${GREEN}    前端 PID: $FRONTEND_PID${NC}"

sleep 1

echo ""
echo -e "${GREEN}==================================="
echo "  系统已启动!"
echo "  前端: http://localhost:8501"
echo "  后端: http://localhost:8080"
echo "  按 Ctrl+C 停止所有服务..."
echo -e "===================================${NC}"
echo ""

# 6. 等待 Ctrl+C，然后清理
cleanup() {
  echo ""
  echo -e "${CYAN}==> 正在停止服务...${NC}"
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  for port in 8080 8501; do
    pid=$(netstat -ano 2>/dev/null | grep ":$port " | grep LISTENING | awk '{print $5}' | head -1) || true
    if [ -n "$pid" ]; then
      taskkill //F //PID "$pid" 2>/dev/null || true
    fi
  done
  echo -e "${GREEN}    服务已停止${NC}"
  exit 0
}
trap cleanup SIGINT SIGTERM

wait
