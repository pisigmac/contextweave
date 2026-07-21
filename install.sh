#!/usr/bin/env bash

set -e

echo "========================================"
echo "      ContextWeave CLI Installer        "
echo "========================================"

# Require Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found."
    exit 1
fi

# Directories
INSTALL_DIR="$HOME/.local/share/contextweave"
VENV_DIR="$INSTALL_DIR/venv"
SRC_DIR="$INSTALL_DIR/src"
BIN_DIR="$HOME/.local/bin"
REPO_URL="https://github.com/username/contextweave.git" # TODO: Update with actual GitHub URL

mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# Install or Update Source
if [ -f "pyproject.toml" ] && grep -q "contextweave" pyproject.toml; then
    echo "=> Installing from local source directory..."
    SOURCE_PATH="$(pwd)"
else
    echo "=> Downloading ContextWeave source..."
    if command -v git &> /dev/null; then
        if [ -d "$SRC_DIR" ]; then
            echo "=> Updating existing repository..."
            cd "$SRC_DIR"
            git pull origin main --quiet
            SOURCE_PATH="$SRC_DIR"
        else
            echo "=> Cloning repository..."
            git clone --quiet "$REPO_URL" "$SRC_DIR"
            SOURCE_PATH="$SRC_DIR"
        fi
    else
        echo "Error: git is required to download ContextWeave."
        exit 1
    fi
fi

# Setup Virtual Environment
echo "=> Setting up isolated Python environment..."
python3 -m venv "$VENV_DIR"

# Install package
echo "=> Installing dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -e "$SOURCE_PATH"

# Create symlink
echo "=> Creating 'weave' command..."
ln -sf "$VENV_DIR/bin/weave" "$BIN_DIR/weave"

echo ""
echo "========================================"
echo "  ContextWeave Installed Successfully!  "
echo "========================================"
echo ""
echo "The 'weave' executable is located at:"
echo "  $BIN_DIR/weave"
echo ""

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "⚠️  NOTE: '$BIN_DIR' is not in your PATH."
    echo "Please add it to your shell profile (e.g. ~/.bashrc or ~/.zshrc):"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

echo "To get started, run:"
echo "  weave --help"
