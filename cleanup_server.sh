#!/bin/bash

echo "🔧 Cleaning up server processes and freeing port 3000..."

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Kill any Python processes running server_fastapi.py
echo "📋 Looking for server_fastapi.py processes..."
SERVER_PIDS=$(pgrep -f "server_fastapi.py" 2>/dev/null)
if [ -n "$SERVER_PIDS" ]; then
    echo "🔄 Found server processes: $SERVER_PIDS"
    for pid in $SERVER_PIDS; do
        echo "🔄 Terminating server process (PID: $pid)..."
        kill -TERM "$pid" 2>/dev/null
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            echo "🔄 Force killing server process (PID: $pid)..."
            kill -KILL "$pid" 2>/dev/null
        fi
    done
    echo "✅ Killed server processes"
else
    echo "ℹ️ No server_fastapi.py processes found"
fi

# Method 1: Use fuser to kill processes on port 3000
echo "📋 Using fuser to kill processes on port 3000..."
if command_exists fuser; then
    if fuser -k 3000/tcp 2>/dev/null; then
        echo "✅ fuser killed processes on port 3000"
    else
        echo "ℹ️ fuser found no processes on port 3000"
    fi
else
    echo "⚠️ fuser not available"
fi

# Method 2: Use lsof to find and kill processes
echo "📋 Using lsof to find and kill processes on port 3000..."
if command_exists lsof; then
    PORT_PIDS=$(lsof -ti:3000 2>/dev/null)
    if [ -n "$PORT_PIDS" ]; then
        echo "🔄 Found processes using port 3000: $PORT_PIDS"
        for pid in $PORT_PIDS; do
            echo "🔄 Killing process (PID: $pid)..."
            kill -TERM "$pid" 2>/dev/null
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                echo "🔄 Force killing process (PID: $pid)..."
                kill -KILL "$pid" 2>/dev/null
            fi
        done
        echo "✅ Killed processes using lsof"
    else
        echo "ℹ️ lsof found no processes on port 3000"
    fi
else
    echo "⚠️ lsof not available"
fi

# Method 3: Use ss to find and kill processes
echo "📋 Using ss to find and kill processes on port 3000..."
if command_exists ss; then
    SS_OUTPUT=$(ss -tlnp | grep ":3000" 2>/dev/null)
    if [ -n "$SS_OUTPUT" ]; then
        echo "🔄 Found processes using ss: $SS_OUTPUT"
        echo "$SS_OUTPUT" | while read -r line; do
            if [[ $line =~ pid=([0-9]+) ]]; then
                pid="${BASH_REMATCH[1]}"
                echo "🔄 Killing process (PID: $pid)..."
                kill -TERM "$pid" 2>/dev/null
                sleep 1
                if kill -0 "$pid" 2>/dev/null; then
                    echo "🔄 Force killing process (PID: $pid)..."
                    kill -KILL "$pid" 2>/dev/null
                fi
            fi
        done
        echo "✅ Killed processes using ss"
    else
        echo "ℹ️ ss found no processes on port 3000"
    fi
else
    echo "⚠️ ss not available"
fi

# Method 4: Use netstat as fallback
echo "📋 Using netstat to find and kill processes on port 3000..."
if command_exists netstat; then
    NETSTAT_OUTPUT=$(netstat -tlnp 2>/dev/null | grep ":3000" 2>/dev/null)
    if [ -n "$NETSTAT_OUTPUT" ]; then
        echo "🔄 Found processes using netstat: $NETSTAT_OUTPUT"
        echo "$NETSTAT_OUTPUT" | while read -r line; do
            if [[ $line =~ ([0-9]+)/ ]]; then
                pid="${BASH_REMATCH[1]}"
                echo "🔄 Killing process (PID: $pid)..."
                kill -TERM "$pid" 2>/dev/null
                sleep 1
                if kill -0 "$pid" 2>/dev/null; then
                    echo "🔄 Force killing process (PID: $pid)..."
                    kill -KILL "$pid" 2>/dev/null
                fi
            fi
        done
        echo "✅ Killed processes using netstat"
    else
        echo "ℹ️ netstat found no processes on port 3000"
    fi
else
    echo "⚠️ netstat not available"
fi

# Wait for processes to fully terminate
echo "⏳ Waiting for processes to terminate..."
sleep 3

# Check if port 3000 is now free
echo "🔍 Checking if port 3000 is now available..."
if command_exists nc; then
    if nc -z localhost 3000 2>/dev/null; then
        echo "⚠️ Port 3000 is still in use"
    else
        echo "✅ Port 3000 is now available"
    fi
elif command_exists telnet; then
    if timeout 1 telnet localhost 3000 2>/dev/null | grep -q "Connected"; then
        echo "⚠️ Port 3000 is still in use"
    else
        echo "✅ Port 3000 is now available"
    fi
else
    echo "ℹ️ Cannot test port availability (nc/telnet not available)"
fi

echo "🎉 Cleanup completed!" 