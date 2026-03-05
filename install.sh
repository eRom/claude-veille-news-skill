#!/usr/bin/env bash
# install.sh — Installe la skill What About dans Claude Code
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$HOME/.claude/skills/what-about"

echo "=== What About — Installation ==="
echo ""

# Creer le dossier skill
mkdir -p "$SKILL_DIR/references"

# Copier SKILL.md
cp "$SCRIPT_DIR/SKILL.md" "$SKILL_DIR/SKILL.md"
echo "[OK] SKILL.md copie"

# Copier les references
for ref in orchestration.md notebooklm_integration.md sources_guide.md; do
    if [ -f "$SCRIPT_DIR/references/$ref" ]; then
        cp "$SCRIPT_DIR/references/$ref" "$SKILL_DIR/references/$ref"
        echo "[OK] references/$ref copie"
    fi
done

echo ""
echo "=== Installation terminee ==="
echo "Skill installee dans : $SKILL_DIR"
echo ""
echo "Pour utiliser : /what-about veille llm-ai-agents"
