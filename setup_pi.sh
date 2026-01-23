#!/bin/bash
# Quick setup script for Raspberry Pi

echo "=========================================="
echo "MikroTik PisoNet - Raspberry Pi Setup"
echo "=========================================="

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "⚠ Warning: This doesn't appear to be a Raspberry Pi"
fi

# Install system dependencies
echo ""
echo "[1/5] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv

# Create virtual environment
echo ""
echo "[2/5] Creating Python virtual environment..."
python3 -m venv env
source env/bin/activate

# Install Python packages
echo ""
echo "[3/5] Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Setup .env file if it doesn't exist
echo ""
echo "[4/5] Checking configuration..."
if [ ! -f .env ]; then
    echo "⚠ .env file not found. Creating from template..."
    cat > .env << 'EOF'
# Flask Configuration
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///pisonet.db

# MikroTik Router Configuration
MIKROTIK_HOST=192.168.88.1
MIKROTIK_USERNAME=admin
MIKROTIK_PASSWORD=12345
MIKROTIK_PORT=8728
MIKROTIK_USE_SSL=False

# Flask Server
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# WAN Interface
MIKROTIK_WAN_INTERFACE=wlan1
EOF
    echo "✓ Created .env file. Please edit it with your MikroTik credentials:"
    echo "  nano .env"
else
    echo "✓ .env file already exists"
fi

# Test MikroTik connection
echo ""
echo "[5/5] Testing MikroTik connection..."
python3 test_mikrotik_connection.py

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To start the server:"
echo "  source env/bin/activate"
echo "  python3 run.py"
echo ""
echo "Or run in background:"
echo "  nohup python3 run.py > server.log 2>&1 &"
echo ""
echo "Access dashboard at: http://[YOUR_PI_IP]:5000"
echo ""
