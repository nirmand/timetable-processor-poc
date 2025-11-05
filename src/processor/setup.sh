#!/bin/bash
# Setup script for processor-engine development environment

cd "$(dirname "$0")"

echo "🔧 Setting up processor-engine environment..."

# Check if Python 3.12+ is available
python_version=$(python --version 2>&1 | grep -oP '(?<=Python )\d+\.\d+')
echo "✓ Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
if [ -f "venv/Scripts/activate" ]; then
    # Windows
    source venv/Scripts/activate
else
    # Unix/Linux/Mac
    source venv/bin/activate
fi

echo "✓ Virtual environment activated"

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install dependencies
echo "📦 Installing dependencies and development tools..."
pip install -e ".[dev]"

echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Activate the virtual environment:"
echo "      On Windows (PowerShell): .\\venv\\Scripts\\Activate.ps1"
echo "      On Windows (CMD): .\\venv\\Scripts\\activate.bat"
echo "      On Unix/Linux/Mac: source venv/bin/activate"
echo ""
echo "   2. Run the processor:"
echo "      python scripts/run.py /path/to/timetable.png"
