#!/usr/bin/env bash
# install.sh — Installe la skill What About dans Claude Code
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$HOME/.claude/skills/what-about"

echo "=== What About — Installation ==="
echo ""

# Creer les dossiers
mkdir -p "$SKILL_DIR/references"
mkdir -p "$SKILL_DIR/collectors"
mkdir -p "$SKILL_DIR/config"
mkdir -p "$SKILL_DIR/scripts/lib"

# Copier SKILL.md
cp "$SCRIPT_DIR/SKILL.md" "$SKILL_DIR/SKILL.md"
echo "[OK] SKILL.md copie"

# Copier les collecteurs
for f in "$SCRIPT_DIR"/collectors/*.py; do
    if [ -f "$f" ]; then
        cp "$f" "$SKILL_DIR/collectors/"
        echo "[OK] collectors/$(basename "$f") copie"
    fi
done

# Copier les scripts
for f in "$SCRIPT_DIR"/scripts/*.py; do
    if [ -f "$f" ]; then
        cp "$f" "$SKILL_DIR/scripts/"
        echo "[OK] scripts/$(basename "$f") copie"
    fi
done

# Copier scripts/lib
for f in "$SCRIPT_DIR"/scripts/lib/*.py; do
    if [ -f "$f" ]; then
        cp "$f" "$SKILL_DIR/scripts/lib/"
        echo "[OK] scripts/lib/$(basename "$f") copie"
    fi
done

# Copier les configs
for f in "$SCRIPT_DIR"/config/*.json; do
    if [ -f "$f" ]; then
        cp "$f" "$SKILL_DIR/config/"
        echo "[OK] config/$(basename "$f") copie"
    fi
done

# Copier .env (sans ecraser si deja present)
if [ -f "$SCRIPT_DIR/.env" ]; then
    cp -n "$SCRIPT_DIR/.env" "$SKILL_DIR/.env" 2>/dev/null && echo "[OK] .env copie" || echo "[OK] .env deja present, pas ecrase"
fi
cp "$SCRIPT_DIR/.env.example" "$SKILL_DIR/.env.example"
echo "[OK] .env.example copie"

# Copier les references
for ref in notebooklm_integration.md; do
    if [ -f "$SCRIPT_DIR/references/$ref" ]; then
        cp "$SCRIPT_DIR/references/$ref" "$SKILL_DIR/references/$ref"
        echo "[OK] references/$ref copie"
    fi
done

# Verifier les dependances Python
echo ""
echo "--- Verification des dependances ---"
MISSING=""
for pkg in requests feedparser; do
    if ! python3 -c "import $pkg" 2>/dev/null; then
        MISSING="$MISSING $pkg"
    fi
done

if [ -n "$MISSING" ]; then
    echo "[WARN] Packages manquants :$MISSING"
    echo "       Installer avec : pip3 install$MISSING"
else
    echo "[OK] Toutes les dependances Python sont installees"
fi

echo ""
echo "=== Installation terminee ==="
echo "Skill installee dans : $SKILL_DIR"
echo ""
echo "Pour utiliser : /what-about llm-ai-agents"
