#!/bin/bash

# ===============================================
# WeChat Article API Service - Status Check Script
# ===============================================

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SERVICE_PORT=5000

echo
echo "========================================"
echo " WeChat Article API Service - Status"
echo "========================================"
echo

# Check if running as systemd service
if [ "$EUID" -eq 0 ] && systemctl list-unit-files | grep -q wechat-article-api; then
    echo -e "${BLUE}systemd Service Status:${NC}"
    systemctl status wechat-article-api --no-pager -l
    echo
fi

# Check process
echo -e "${BLUE}Process Status:${NC}"
PIDS=$(pgrep -f "python.*app.py")
if [ -z "$PIDS" ]; then
    PIDS=$(pgrep -f "uvicorn.*app:app")
fi

if [ -n "$PIDS" ]; then
    echo -e "${GREEN}+ Service is running${NC}"
    for PID in $PIDS; do
        echo -e "  PID: $PID"
        ps -p "$PID" -o pid,ppid,user,%cpu,%mem,etime,cmd --no-headers
    done
else
    echo -e "${RED}X Service is not running${NC}"
fi
echo

# Check port
echo -e "${BLUE}Port Status:${NC}"
if command -v netstat &> /dev/null; then
    PORT_CHECK=$(netstat -tulpn 2>/dev/null | grep ":$SERVICE_PORT")
elif command -v ss &> /dev/null; then
    PORT_CHECK=$(ss -tulpn 2>/dev/null | grep ":$SERVICE_PORT")
fi

if [ -n "$PORT_CHECK" ]; then
    echo -e "${GREEN}+ Port $SERVICE_PORT is listening${NC}"
    echo "$PORT_CHECK"
else
    echo -e "${YELLOW}! Port $SERVICE_PORT is not in use${NC}"
fi
echo

# Check API health
echo -e "${BLUE}API Health Check:${NC}"
if command -v curl &> /dev/null; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$SERVICE_PORT/api/health 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        RESPONSE=$(curl -s http://localhost:$SERVICE_PORT/api/health 2>/dev/null)
        echo -e "${GREEN}+ API is healthy${NC}"
        echo "  Response: $RESPONSE"
    else
        echo -e "${RED}X API is not responding (HTTP $HTTP_CODE)${NC}"
    fi
elif command -v wget &> /dev/null; then
    if wget -q --spider http://localhost:$SERVICE_PORT/api/health 2>/dev/null; then
        echo -e "${GREEN}+ API is healthy${NC}"
    else
        echo -e "${RED}X API is not responding${NC}"
    fi
else
    echo -e "${YELLOW}! curl/wget not available, skipping health check${NC}"
fi
echo

# Check login status
echo -e "${BLUE}Login Status:${NC}"
if [ -f ".env" ]; then
    if grep -q "WECHAT_TOKEN=.\+" .env 2>/dev/null; then
        TOKEN_VALUE=$(grep "WECHAT_TOKEN=" .env | cut -d'=' -f2 | head -c 20)
        echo -e "${GREEN}+ WeChat credentials configured${NC}"
        echo "  Token: ${TOKEN_VALUE}..."
        
        EXPIRE_TIME=$(grep "WECHAT_EXPIRE_TIME=" .env | cut -d'=' -f2)
        if [ -n "$EXPIRE_TIME" ] && [ "$EXPIRE_TIME" != "0" ]; then
            CURRENT_TIME=$(date +%s)000
            if [ "$EXPIRE_TIME" -gt "$CURRENT_TIME" ]; then
                echo -e "${GREEN}+ Credentials are valid${NC}"
            else
                echo -e "${YELLOW}! Credentials may be expired${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}! WeChat credentials not configured${NC}"
        echo "  Please visit http://localhost:$SERVICE_PORT/login.html to login"
    fi
else
    echo -e "${YELLOW}! .env file not found${NC}"
fi
echo

# Show access URLs
echo -e "${BLUE}Access URLs:${NC}"
echo "  - Admin Panel: http://localhost:$SERVICE_PORT/admin.html"
echo "  - Login Page:  http://localhost:$SERVICE_PORT/login.html"
echo "  - API Docs:    http://localhost:$SERVICE_PORT/api/docs"
echo "  - Health:      http://localhost:$SERVICE_PORT/api/health"
echo

