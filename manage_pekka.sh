#!/bin/bash

# Configuration
APP_NAME="pekka2000"
APP_PATH="$(pwd)/pekka2000.py"
LOG_FILE="app.log"
PID_FILE=".${APP_NAME}.pid"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if the application is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Function to start the application
start() {
    if is_running; then
        echo -e "${YELLOW}${APP_NAME} is already running with PID $(cat "$PID_FILE")${NC}"
        return
    fi

    echo -e "${GREEN}Starting ${APP_NAME}...${NC}"
    nohup python "$APP_PATH" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo -e "${GREEN}${APP_NAME} started with PID $(cat "$PID_FILE")${NC}"
}

# Function to stop the application
stop() {
    if ! is_running; then
        echo -e "${YELLOW}${APP_NAME} is not running${NC}"
        return
    fi

    echo -e "${YELLOW}Stopping ${APP_NAME}...${NC}"
    pid=$(cat "$PID_FILE")
    kill "$pid"
    rm -f "$PID_FILE"
    echo -e "${GREEN}${APP_NAME} stopped${NC}"
}

# Function to restart the application
restart() {
    stop
    sleep 2
    start
}

# Function to show status
status() {
    if is_running; then
        echo -e "${GREEN}${APP_NAME} is running with PID $(cat "$PID_FILE")${NC}"
    else
        echo -e "${RED}${APP_NAME} is not running${NC}"
    fi
}

# Function to show logs
logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo -e "${RED}Log file not found${NC}"
    fi
}

# Main script logic
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac

exit 0 