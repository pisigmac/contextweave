#!/bin/bash
set -e

echo "Setting up ContextWeave..."

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "Created virtual environment"
fi

source .venv/bin/activate

pip install -e ".[dev]"
echo "Installed dependencies"

mkdir -p workspace
echo "Created workspace directory"

python -c "from services.shared.models import init_db; init_db()"
echo "Initialized database"

echo ""
echo "Setup complete. Run:"
echo "  source .venv/bin/activate"
echo "  weave init 'My Project'"
echo "  weave --help"
