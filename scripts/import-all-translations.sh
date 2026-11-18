#!/bin/bash
# import-all-translations.sh
# Import all frontend and backend translation files
# Run from project root: ./scripts/import-all-translations.sh

set -e

# Get the project root directory
PROJECT_ROOT="$(pwd)"

# Colors for output. $'…' quoting puts the real escape byte in the variable, so a
# call site needs no -e: a plain `echo "...${NC}"` used to print "\033[0m" as the
# four characters and leave the terminal coloured for everything after it.
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
NC=$'\033[0m' # No Color

echo "==========================================="
echo "Importing all translations"
echo "==========================================="

# ============================================================
# Frontend translations
# ============================================================

echo ""
echo -e "${BLUE}📁 Frontend translations${NC}"
echo "-------------------------------------------"

cd "$PROJECT_ROOT/frontend" || { echo -e "${RED}❌ Failed to cd to frontend directory${NC}"; exit 1; }

# Get list of language files in locales directory
# Look for files like en.yaml, es.yaml, de.yaml, etc. (not dynamic, extra, or backend)
LANGUAGE_FILES=$(ls locales/*.yaml 2>/dev/null | grep -v -E "(dynamic|extra|backend)" | sed 's|locales/||' | sed 's|\.yaml$||' | sort)

if [ -z "$LANGUAGE_FILES" ]; then
    echo -e "${RED}❌ No language files found in frontend/locales/${NC}"
    echo "   Looking for files like: en.yaml, es.yaml, de.yaml, etc."
    exit 1
fi

echo "Found frontend language files: $LANGUAGE_FILES"
echo ""

for FILE in $LANGUAGE_FILES; do
    # Extract language code (everything before the first dash or the whole filename if no dash)
    LANG=$(echo "$FILE" | sed 's/-.*$//')
    echo -e "${GREEN}➜ Importing frontend ${LANG} (from ${FILE}.yaml)...${NC}"
    "$PROJECT_ROOT/backend/venv/bin/python" "$PROJECT_ROOT/backend/scripts/import_translations.py" "$LANG" "$PROJECT_ROOT/frontend/locales/${FILE}.yaml"
    echo ""
done

echo -e "${GREEN}✅ Frontend translations complete${NC}"

# ============================================================
# Backend translations
# ============================================================

echo ""
echo -e "${BLUE}📁 Backend translations${NC}"
echo "-------------------------------------------"

cd "$PROJECT_ROOT/backend" || { echo -e "${RED}❌ Failed to cd to backend directory${NC}"; exit 1; }

# Get list of language files in locales directory
BACKEND_LANGUAGE_FILES=$(ls locales/*-backend.yaml 2>/dev/null | sed 's|locales/||' | sed 's|\.yaml$||' | sort)

if [ -z "$BACKEND_LANGUAGE_FILES" ]; then
    echo -e "${YELLOW}⚠️ No backend language files found in backend/locales/${NC}"
    echo "   Looking for files like: en-backend.yaml, es-backend.yaml, etc."
else
    echo "Found backend files: $BACKEND_LANGUAGE_FILES"
    echo ""

    cd "$PROJECT_ROOT/frontend" || { echo -e "${RED}❌ Failed to cd to frontend directory${NC}"; exit 1; }

    for FILE in $BACKEND_LANGUAGE_FILES; do
        # Extract language code (everything before the first dash)
        # For "de-backend" -> "de", "es-backend" -> "es"
        LANG=$(echo "$FILE" | sed 's/-.*$//')
        echo -e "${GREEN}➜ Importing backend ${LANG} (from ${FILE}.yaml)...${NC}"
        "$PROJECT_ROOT/backend/venv/bin/python" "$PROJECT_ROOT/backend/scripts/import_translations.py" "$LANG" "$PROJECT_ROOT/backend/locales/${FILE}.yaml"
        echo ""
    done

    echo -e "${GREEN}✅ Backend translations complete${NC}"
fi

# ============================================================
# Summary
# ============================================================

echo ""
echo "==========================================="
echo -e "${GREEN}✅ All translations imported successfully${NC}"
echo "==========================================="
echo ""
echo "Frontend files: $LANGUAGE_FILES"
if [ -n "$BACKEND_LANGUAGE_FILES" ]; then
    echo "Backend files:  $BACKEND_LANGUAGE_FILES"
else
    echo "Backend files:  (none found)"
fi
echo ""
echo -e "${YELLOW}💡 Note: The frontend translations are now generated from module-level"
echo "   translation files (translations.ts) via the extract-translations.ts script."
echo "   The en.yaml file is the merged output of all module translations.${NC}"