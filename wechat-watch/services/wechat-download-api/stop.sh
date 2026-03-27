#!/bin/bash

# ===============================================
# WeChat Article API Service - Stop Script
# ===============================================

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo
echo "========================================"
echo " WeChat Article API Service - Stop"
echo "========================================"
echo

# Check if running as systemd service
if [ "$EUID" -eq 0 ] && systemctl is-active --quiet wechat-article-api; then
    echo -e "${BLUE}Detected systemd service, stopping...${NC}"
    systemctl stop wechat-article-api
    echo -e "${GREEN}+ systemd service stopped${NC}"
    echo
    exit 0
fi

# Find and kill process
echo -e "${BLUE}Searching for running API service...${NC}"

# Try to find by app.py
PIDS=$(pgrep -f "python.*app.py")

if [ -z "$PIDS" ]; then
    # Try to find by uvicorn
    PIDS=$(pgrep -f "uvicorn.*app:app")
fi

if [ -z "$PIDS" ]; then
    echo -e "${YELLOW}! No running service found${NC}"
    echo
    exit 0
fi

echo -e "${BLUE}Found process(es): $PIDS${NC}"

# Kill processes
for PID in $PIDS; do
    echo -e "${BLUE}Stopping process $PID...${NC}"
    kill "$PID" 2>/dev/null
    
    # Wait for graceful shutdown
    sleep 2
    
    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}! Process still running, force killing...${NC}"
        kill -9 "$PID" 2>/dev/null
    fi
    
    echo -e "${GREEN}+ Process $PID stopped${NC}"
done

echo
echo -e "${GREEN}Service stopped successfully${NC}"
echo

