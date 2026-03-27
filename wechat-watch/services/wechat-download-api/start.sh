#!/bin/bash

# ===============================================
# WeChat Article API Service - Linux Deployment Script v2.0
# ===============================================

# Error handling
set -e  # Exit on error
set -o pipefail  # Catch errors in pipes

# Trap errors
trap 'echo -e "\n${RED}Error: Deployment failed at line $LINENO${NC}" >&2; exit 1' ERR

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
PROJECT_NAME="wechat-article-api"
SERVICE_PORT=5000
PYTHON_VERSION="3.8"
VENV_NAME="venv"
DEPLOY_USER="wechat-api"  # Dedicated service user

# Get current directory (compatible with different shells)
if [ -n "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi
INSTALL_DIR="$SCRIPT_DIR"
LOG_DIR="$INSTALL_DIR/logs"

# Get the actual user who ran sudo (if applicable)
if [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
else
    REAL_USER="$USER"
fi

# ===============================================
# Parse command line arguments
# ===============================================
AUTO_MODE=false

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --auto)
                AUTO_MODE=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --auto    Non-interactive mode (auto-select standard mode)"
                echo "  --help    Show this help message"
                echo ""
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

# ===============================================
# Show welcome message
# ===============================================
show_welcome() {
    echo
    echo "========================================"
    echo " WeChat Article API Deployment Tool v1.0.0"
    echo "========================================"
    echo
    echo -e "${BLUE}Installation directory: $INSTALL_DIR${NC}"
    echo -e "${BLUE}Service port: $SERVICE_PORT${NC}"
    echo -e "${BLUE}Service user: $DEPLOY_USER${NC}"
    echo
}

# ===============================================
# Check permissions
# ===============================================
check_permission() {
    echo -e "${BLUE}Checking system and permissions...${NC}"
    
    # Detect OS
    if [ -f /etc/os-release ]; then
        . /etc/os-release 2>/dev/null || true
        echo -e "${GREEN}+ OS: ${NAME:-Linux} ${VERSION_ID:-unknown}${NC}"
    fi
    
    # Check if running in container
    if [ -f /.dockerenv ] || grep -qa container /proc/1/environ 2>/dev/null; then
        echo -e "${YELLOW}! Container environment detected${NC}"
    fi
    
    if [ "$EUID" -ne 0 ]; then 
        echo -e "${YELLOW}! Running without root privileges${NC}"
        echo -e "${YELLOW}  - Dedicated service user will NOT be created${NC}"
        echo -e "${YELLOW}  - Systemd service will NOT be configured${NC}"
        echo -e "${YELLOW}  - For full deployment, run: sudo bash start.sh${NC}"
        echo
        # Skip interactive prompt in auto mode
        if [ "$AUTO_MODE" = false ]; then
            echo -e "${YELLOW}Press Enter to continue or Ctrl+C to exit${NC}"
            read -p ""
        fi
    else
        echo -e "${GREEN}+ Running with root privileges${NC}"
    fi
    echo
}

# ===============================================
# Step 1: Check Python
# ===============================================
check_python() {
    echo -e "${BLUE}[1/7] Checking Python environment...${NC}"
    
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}X Python3 not found${NC}"
        echo "Please install Python $PYTHON_VERSION or higher"
        exit 1
    fi

    PYTHON_VER=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}+ Python version: $PYTHON_VER${NC}"
    
    # Check venv module
    if ! python3 -m venv --help &> /dev/null; then
        echo -e "${YELLOW}! python3-venv not found${NC}"
        
        if [ "$EUID" -eq 0 ]; then
            echo -e "${BLUE}  Installing python3-venv...${NC}"
            
            # Detect package manager and install
            if command -v apt &> /dev/null; then
                # Debian/Ubuntu
                apt update && apt install -y python3-venv python3-pip || {
                    echo -e "${RED}X Failed to install python3-venv${NC}"
                    echo "Please run: apt install python3-venv python3-pip"
                    exit 1
                }
            elif command -v yum &> /dev/null; then
                # RHEL/CentOS
                yum install -y python3-venv python3-pip || {
                    echo -e "${RED}X Failed to install python3-venv${NC}"
                    echo "Please run: yum install python3-venv python3-pip"
                    exit 1
                }
            elif command -v dnf &> /dev/null; then
                # Fedora
                dnf install -y python3-venv python3-pip || {
                    echo -e "${RED}X Failed to install python3-venv${NC}"
                    echo "Please run: dnf install python3-venv python3-pip"
                    exit 1
                }
            else
                echo -e "${RED}X Cannot determine package manager${NC}"
                echo "Please install python3-venv manually"
                exit 1
            fi
            echo -e "${GREEN}+ python3-venv installed${NC}"
        else
            echo -e "${RED}X python3-venv is required but not installed${NC}"
            echo
            echo "Please run one of the following commands with sudo:"
            echo "  Debian/Ubuntu: sudo apt install python3-venv python3-pip"
            echo "  RHEL/CentOS:   sudo yum install python3-venv python3-pip"
            echo "  Fedora:        sudo dnf install python3-venv python3-pip"
            echo
            echo "Then run this script again"
            exit 1
        fi
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
        echo -e "${YELLOW}! pip not found, attempting to install...${NC}"
        python3 -m ensurepip --upgrade 2>/dev/null || {
            if [ "$EUID" -eq 0 ]; then
                if command -v apt &> /dev/null; then
                    apt install -y python3-pip
                elif command -v yum &> /dev/null; then
                    yum install -y python3-pip
                elif command -v dnf &> /dev/null; then
                    dnf install -y python3-pip
                fi
            fi
        }
    fi
    echo -e "${GREEN}+ pip available${NC}"
    echo
}

# ===============================================
# Step 2: Create virtual environment
# ===============================================
create_venv() {
    echo -e "${BLUE}[2/7] Creating Python virtual environment...${NC}"
    
    # Use .venv as default (preferred over venv)
    if [[ -d ".venv" ]]; then
        VENV_NAME=".venv"
        echo -e "${GREEN}+ Using existing virtual environment: .venv${NC}"
    elif [[ -d "venv" ]]; then
        VENV_NAME="venv"
        echo -e "${YELLOW}! Using existing virtual environment: venv${NC}"
    else
        VENV_NAME=".venv"
        python3 -m venv "$VENV_NAME"
        echo -e "${GREEN}+ Virtual environment created: $VENV_NAME${NC}"
    fi
    
    # Activate virtual environment
    source "$VENV_NAME/bin/activate"
    echo -e "${GREEN}+ Virtual environment activated${NC}"
    echo
}

# ===============================================
# Step 3: Install dependencies
# ===============================================
install_dependencies() {
    echo -e "${BLUE}[3/7] Installing Python dependencies...${NC}"
    
    # Upgrade pip
    python -m pip install --upgrade pip
    
    # Install requirements.txt
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        echo
        # Verify installation
        if ! python -c "import fastapi" 2>/dev/null; then
            echo -e "${RED}X Dependencies installation failed${NC}"
            exit 1
        fi
        echo -e "${GREEN}+ Dependencies installed successfully${NC}"
    else
        echo -e "${YELLOW}! requirements.txt not found, installing core dependencies${NC}"
        pip install fastapi uvicorn httpx python-dotenv
        echo
        # Verify installation
        if ! python -c "import fastapi" 2>/dev/null; then
            echo -e "${RED}X Core dependencies installation failed${NC}"
            exit 1
        fi
        echo -e "${GREEN}+ Core dependencies installed successfully${NC}"
    fi
    echo
}

# ===============================================
# Step 4: Initialize project
# ===============================================
initialize_project() {
    echo -e "${BLUE}[4/7] Initializing project...${NC}"
    
    # Create necessary directories
    mkdir -p static logs
    echo -e "${GREEN}+ Directory structure created${NC}"
    
    # Create .env file if not exists
    if [[ ! -f ".env" ]]; then
        echo -e "${YELLOW}! .env file not found, creating from template...${NC}"
        
        if [[ -f "env.example" ]]; then
            cp env.example .env
            echo -e "${GREEN}+ .env file created from env.example${NC}"
        else
            echo -e "${YELLOW}! env.example not found, creating basic .env file...${NC}"
            cat > .env << 'EOF'
# WeChat Article API Configuration
# Auto-generated by start.sh

# Authentication Info (Auto-filled after login)
WECHAT_TOKEN=
WECHAT_COOKIE=
WECHAT_FAKEID=
WECHAT_NICKNAME=
WECHAT_EXPIRE_TIME=

# Webhook Configuration
WEBHOOK_URL=
WEBHOOK_NOTIFICATION_INTERVAL=300

# Rate Limiting
RATE_LIMIT_GLOBAL=10
RATE_LIMIT_PER_IP=5
RATE_LIMIT_ARTICLE_INTERVAL=3
EOF
            echo -e "${GREEN}+ Basic .env file created${NC}"
        fi
        
        echo
        echo -e "${YELLOW}========================================${NC}"
        echo -e "${YELLOW}  First-time Setup${NC}"
        echo -e "${YELLOW}========================================${NC}"
        echo
        echo -e "${GREEN}Next Steps:${NC}"
        echo "  1. Service will start after deployment"
        echo "  2. Visit: http://localhost:$SERVICE_PORT/login.html"
        echo "  3. Scan QR code with WeChat"
        echo "  4. Login credentials will be saved automatically"
        echo
        echo -e "${YELLOW}========================================${NC}"
        echo
    else
        echo -e "${GREEN}+ .env configuration file found${NC}"
        
        # Check if credentials are actually configured (not empty)
        if grep -q "WECHAT_TOKEN=.\+" .env 2>/dev/null; then
            echo -e "${GREEN}+ WeChat login credentials configured${NC}"
        else
            echo -e "${YELLOW}! WeChat credentials not configured yet${NC}"
            echo -e "${YELLOW}  Please visit http://localhost:$SERVICE_PORT/login.html to login${NC}"
        fi
    fi
    echo
}

# ===============================================
# Step 5: Start service (non-root mode)
# ===============================================
start_service() {
    echo -e "${BLUE}[5/7] Starting service...${NC}"
    
    # If running with root, service will be started via systemd
    if [ "$EUID" -eq 0 ]; then
        echo -e "${YELLOW}! Service will be started via systemd (see step 7)${NC}"
        echo
        return
    fi
    
    # For non-root users, start service directly
    if [ "$AUTO_MODE" = true ]; then
        # Auto mode: start in background and show URLs
        echo
        echo "========================================"
        echo -e "${GREEN}Service Startup Information (Auto Mode)${NC}"
        echo "========================================"
        echo
        echo -e "${BLUE}Access URLs:${NC}"
        echo "  - Admin Panel: http://localhost:$SERVICE_PORT/admin.html"
        echo "  - Login Page:  http://localhost:$SERVICE_PORT/login.html"
        echo "  - API Docs:    http://localhost:$SERVICE_PORT/api/docs"
        echo "  - Health:      http://localhost:$SERVICE_PORT/api/health"
        echo
        
        # Check if service is already running
        if pgrep -f "python3 app.py" > /dev/null; then
            echo -e "${YELLOW}! Service is already running${NC}"
            echo -e "${GREEN}+ Access URLs above${NC}"
            echo
            return
        fi
        
        # Start the service in background
        nohup python app.py > "$LOG_DIR/app.log" 2>&1 &
        local PID=$!
        echo -e "${GREEN}+ Service started in background (PID: $PID)${NC}"
        echo -e "${BLUE}  Log file: $LOG_DIR/app.log${NC}"
        echo
        
        # Wait a moment and check if service is healthy
        sleep 2
        if curl -s "http://localhost:$SERVICE_PORT/api/health" > /dev/null 2>&1; then
            echo -e "${GREEN}+ Service is healthy${NC}"
        else
            echo -e "${YELLOW}! Service may still be starting, check logs: tail -f $LOG_DIR/app.log${NC}"
        fi
        echo
        return
    fi
    
    # Interactive mode: start in foreground
    echo
    echo "========================================"
    echo -e "${GREEN}Service Startup Information${NC}"
    echo "========================================"
    echo
    echo -e "${BLUE}Access URLs:${NC}"
    echo "  - Admin Panel: http://localhost:$SERVICE_PORT/admin.html"
    echo "  - Login Page:  http://localhost:$SERVICE_PORT/login.html"
    echo "  - API Docs:    http://localhost:$SERVICE_PORT/api/docs"
    echo "  - ReDoc:       http://localhost:$SERVICE_PORT/api/redoc"
    echo "  - Health:      http://localhost:$SERVICE_PORT/api/health"
    echo
    echo -e "${BLUE}Core Features:${NC}"
    echo "  + Article Retrieval - POST /api/article"
    echo "  + Article List - GET /api/public/articles"
    echo "  + Article Search - GET /api/public/articles/search"
    echo "  + Account Search - GET /api/public/searchbiz"
    echo "  + Image Proxy - GET /api/image"
    echo "  + Auto Rate Limiting"
    echo "  + Webhook Notifications"
    echo
    echo -e "${YELLOW}First time? Please visit login page to scan QR code:${NC}"
    echo "  => http://localhost:$SERVICE_PORT/login.html"
    echo
    echo -e "${YELLOW}Tip: Press Ctrl+C to stop service${NC}"
    echo "========================================"
    echo
    
    # Start the service
    python app.py
}

# ===============================================
# Step 6: Create dedicated service user (optional)
# ===============================================
create_service_user() {
    echo -e "${BLUE}[6/7] Creating dedicated service user...${NC}"
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}! Not running as root, skipping user creation${NC}"
        echo -e "${YELLOW}! Service will run as: $REAL_USER${NC}"
        DEPLOY_USER="$REAL_USER"
        echo
        return
    fi
    
    # Check if user already exists
    if id "$DEPLOY_USER" &>/dev/null; then
        echo -e "${GREEN}+ Service user already exists: $DEPLOY_USER${NC}"
    else
        # Try to create system user
        echo -e "${BLUE}  Creating user $DEPLOY_USER...${NC}"
        
        # Try different methods depending on the system
        if command -v useradd &>/dev/null; then
            # Most Linux distributions
            if useradd -r -s /usr/sbin/nologin -c "WeChat Article API Service" "$DEPLOY_USER" 2>/dev/null; then
                echo -e "${GREEN}+ Created service user: $DEPLOY_USER${NC}"
            elif useradd -r -s /bin/false -c "WeChat Article API Service" "$DEPLOY_USER" 2>/dev/null; then
                echo -e "${GREEN}+ Created service user: $DEPLOY_USER${NC}"
            else
                echo -e "${YELLOW}! User creation failed, trying with adduser...${NC}"
                if command -v adduser &>/dev/null; then
                    adduser --system --no-create-home --group "$DEPLOY_USER" 2>/dev/null || {
                        echo -e "${YELLOW}! All user creation methods failed, using current user: $REAL_USER${NC}"
                        DEPLOY_USER="$REAL_USER"
                    }
                else
                    echo -e "${YELLOW}! Using current user: $REAL_USER${NC}"
                    DEPLOY_USER="$REAL_USER"
                fi
            fi
        else
            echo -e "${YELLOW}! useradd not found, using current user: $REAL_USER${NC}"
            DEPLOY_USER="$REAL_USER"
        fi
    fi
    
    # Set proper ownership
    if [ "$DEPLOY_USER" != "$REAL_USER" ]; then
        echo -e "${BLUE}  Setting file ownership...${NC}"
        if chown -R "$DEPLOY_USER:$DEPLOY_USER" "$INSTALL_DIR" 2>/dev/null; then
            echo -e "${GREEN}+ Ownership set to: $DEPLOY_USER${NC}"
        else
            echo -e "${YELLOW}! Warning: Could not set ownership, trying with group only...${NC}"
            if getent group "$DEPLOY_USER" &>/dev/null; then
                chown -R "$DEPLOY_USER:$DEPLOY_USER" "$INSTALL_DIR" 2>/dev/null || {
                    echo -e "${YELLOW}! Warning: File ownership not changed${NC}"
                }
            fi
        fi
    fi
    
    echo
}

# ===============================================
# Step 7: Configure systemd service (optional)
# ===============================================
configure_systemd() {
    echo -e "${BLUE}[7/7] Configuring systemd service...${NC}"
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}! Not running as root, skipping systemd configuration${NC}"
        echo -e "${YELLOW}! To configure systemd, run: sudo bash start.sh${NC}"
        echo
        return
    fi
    
    # Create systemd service file
    cat > /etc/systemd/system/wechat-article-api.service << EOF
[Unit]
Description=WeChat Article API Service
After=network.target

[Service]
Type=simple
User=$DEPLOY_USER
Group=$DEPLOY_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/$VENV_NAME/bin"
ExecStart=$INSTALL_DIR/$VENV_NAME/bin/python $INSTALL_DIR/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wechat-article-api

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_DIR/logs
ReadWritePaths=$INSTALL_DIR/.env
ReadWritePaths=$INSTALL_DIR/static/qrcodes

[Install]
WantedBy=multi-user.target
EOF
    
    echo -e "${GREEN}+ systemd service file created${NC}"
    
    # Reload systemd configuration
    systemctl daemon-reload
    
    # Ask if user wants to start service now
    read -p "Enable and start systemd service now? (y/N): " START_SERVICE
    if [[ "$START_SERVICE" =~ ^[Yy]$ ]]; then
        systemctl enable wechat-article-api.service
        systemctl start wechat-article-api.service
        echo -e "${GREEN}+ Service started${NC}"
        
        # Show service status
        echo
        echo -e "${BLUE}Service status:${NC}"
        systemctl status wechat-article-api --no-pager || true
    else
        echo -e "${YELLOW}! Service start skipped, you can start it manually later${NC}"
    fi
    echo
}

# ===============================================
# Show deployment summary
# ===============================================
show_summary() {
    echo
    echo "========================================"
    echo -e "${GREEN}Deployment completed!${NC}"
    echo "========================================"
    echo
    echo -e "${GREEN}Deployment Information:${NC}"
    echo "  - Installation directory: $INSTALL_DIR"
    echo "  - Service port: $SERVICE_PORT"
    echo "  - Service user: $DEPLOY_USER"
    echo "  - Virtual environment: $VENV_NAME"
    echo "  - Log directory: $LOG_DIR"
    echo
    echo -e "${GREEN}Usage:${NC}"
    if [ "$EUID" -ne 0 ]; then
        echo "  - Restart: ./start.sh"
        echo "  - Stop: Press Ctrl+C or use ./stop.sh"
        echo "  - Status: ./status.sh"
        echo "  - Activate venv: source venv/bin/activate"
    fi
    echo
    
    if [ "$EUID" -eq 0 ]; then
        echo -e "${GREEN}systemd Commands:${NC}"
        echo "  - Start service: systemctl start wechat-article-api"
        echo "  - Stop service: systemctl stop wechat-article-api"
        echo "  - Restart service: systemctl restart wechat-article-api"
        echo "  - View status: systemctl status wechat-article-api"
        echo "  - View logs: journalctl -u wechat-article-api -f"
        echo
    fi
    
    echo -e "${GREEN}Access URLs:${NC}"
    echo "  - Admin Panel: http://localhost:$SERVICE_PORT/admin.html"
    echo "  - Login Page: http://localhost:$SERVICE_PORT/login.html"
    echo "  - API Documentation: http://localhost:$SERVICE_PORT/api/docs"
    echo "  - ReDoc: http://localhost:$SERVICE_PORT/api/redoc"
    echo "  - Health Check: http://localhost:$SERVICE_PORT/api/health"
    echo
    echo -e "${GREEN}Core Features:${NC}"
    echo "  + Article Retrieval - POST /api/article"
    echo "  + Article List - GET /api/public/articles"
    echo "  + Article Search - GET /api/public/articles/search"
    echo "  + Account Search - GET /api/public/searchbiz"
    echo "  + Image Proxy - GET /api/image"
    echo "  + Auto Rate Limiting"
    echo "  + Webhook Notifications"
    echo
    echo -e "${YELLOW}Notes:${NC}"
    echo "  - First-time login required via web interface"
    echo "  - Credentials saved in .env file"
    echo "  - Check port usage: netstat -tulpn | grep :$SERVICE_PORT"
    echo
}

# ===============================================
# Main function
# ===============================================
main() {
    # Parse command line arguments
    parse_args "$@"
    
    show_welcome
    check_permission
    check_python
    create_venv
    install_dependencies
    initialize_project
    start_service       # Non-root: start service directly; Root: skip (use systemd)
    create_service_user # Root only: create dedicated user
    configure_systemd   # Root only: configure systemd service
    show_summary
}

# Run main function with all arguments
main "$@"
