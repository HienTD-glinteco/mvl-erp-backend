#!/bin/bash

# Script to reorganize test files from tests/ to their corresponding app/libs directories
# This consolidates all tests into their respective modules

set -e  # Exit on error

echo "========================================="
echo "Test Files Reorganization Script"
echo "========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to move directory
move_directory() {
    local src=$1
    local dest=$2

    if [ -d "$src" ]; then
        echo -e "${BLUE}Moving:${NC} $src -> $dest"

        # Create destination if it doesn't exist
        mkdir -p "$dest"

        # Move all files from source to destination
        if [ "$(ls -A $src)" ]; then
            # Copy files (in case of conflicts, we'll handle manually)
            cp -rn "$src"/* "$dest/" 2>/dev/null || {
                echo -e "${YELLOW}Warning: Some files may already exist in $dest${NC}"
                # Try to merge
                rsync -av --ignore-existing "$src"/ "$dest/"
            }
            echo -e "${GREEN}✓ Moved${NC}"
        else
            echo -e "${YELLOW}  (empty directory, skipped)${NC}"
        fi
    else
        echo -e "${YELLOW}Skip: $src (not found)${NC}"
    fi
}

# Function to move single file
move_file() {
    local src=$1
    local dest_dir=$2
    local filename=$(basename "$src")

    if [ -f "$src" ]; then
        echo -e "${BLUE}Moving:${NC} $src -> $dest_dir/$filename"
        mkdir -p "$dest_dir"

        if [ -f "$dest_dir/$filename" ]; then
            echo -e "${YELLOW}Warning: $dest_dir/$filename already exists. Skipping...${NC}"
        else
            mv "$src" "$dest_dir/"
            echo -e "${GREEN}✓ Moved${NC}"
        fi
    fi
}

echo "Step 1: Moving tests/apps/* to apps/*/tests/"
echo "================================================"

# Move core tests
move_directory "tests/apps/core" "apps/core/tests"

# Move hrm tests
move_directory "tests/apps/hrm" "apps/hrm/tests"

# Move notifications tests
move_directory "tests/apps/notifications" "apps/notifications/tests"

# Move payroll tests
move_directory "tests/apps/payroll" "apps/payroll/tests"

echo ""
echo "Step 2: Moving tests/libs/* to libs/tests/"
echo "================================================"

# Move libs tests
move_directory "tests/libs" "libs/tests"

echo ""
echo "Step 3: Moving root-level test files"
echo "================================================"

# Determine where root-level tests should go based on their content
# test_reports_hr_helpers.py -> apps/hrm/tests/
# test_reports_recruitment_helpers.py -> apps/hrm/tests/
# test_check_no_vietnamese.py -> libs/tests/ or tests/ (keep as is)

if [ -f "tests/test_reports_hr_helpers.py" ]; then
    move_file "tests/test_reports_hr_helpers.py" "apps/hrm/tests"
fi

if [ -f "tests/test_reports_recruitment_helpers.py" ]; then
    move_file "tests/test_reports_recruitment_helpers.py" "apps/hrm/tests"
fi

# Keep test_check_no_vietnamese.py in a general tests folder since it's a project-wide check
echo -e "${BLUE}Note:${NC} tests/test_check_no_vietnamese.py - keeping in tests/ (project-wide check)"

echo ""
echo "Step 4: Moving fixtures"
echo "================================================"

# Check if fixtures should be moved to a central location or kept
if [ -d "tests/fixtures" ]; then
    # Create a shared fixtures directory that can be accessed by all tests
    mkdir -p "tests/fixtures"  # Keep it in tests/ for now as it's shared
    echo -e "${GREEN}✓ Fixtures kept in tests/fixtures (shared resource)${NC}"
fi

echo ""
echo "Step 5: Cleanup empty directories"
echo "================================================"

# Function to remove empty directories
cleanup_empty_dirs() {
    local dir=$1
    if [ -d "$dir" ]; then
        # Remove empty subdirectories
        find "$dir" -type d -empty -delete 2>/dev/null || true

        # Check if directory itself is now empty (except for __pycache__)
        if [ -z "$(ls -A $dir | grep -v __pycache__)" ]; then
            echo -e "${YELLOW}Removing empty directory: $dir${NC}"
            rm -rf "$dir"
        fi
    fi
}

cleanup_empty_dirs "tests/apps/core"
cleanup_empty_dirs "tests/apps/hrm"
cleanup_empty_dirs "tests/apps/notifications"
cleanup_empty_dirs "tests/apps/payroll"
cleanup_empty_dirs "tests/apps"
cleanup_empty_dirs "tests/libs"

echo ""
echo "========================================="
echo "Summary"
echo "========================================="
echo -e "${GREEN}✓ Tests reorganized successfully!${NC}"
echo ""
echo "Test locations:"
echo "  • apps/core/tests/       - Core app tests"
echo "  • apps/hrm/tests/        - HRM app tests"
echo "  • apps/notifications/tests/ - Notifications tests"
echo "  • apps/payroll/tests/    - Payroll app tests"
echo "  • libs/tests/            - Shared library tests"
echo "  • tests/                 - Project-wide tests and fixtures"
echo ""
echo "Next steps:"
echo "  1. Update pytest.ini if needed"
echo "  2. Run tests to verify: poetry run pytest"
echo "  3. Update CI/CD configuration if paths changed"
echo "  4. Remove tests/apps and tests/libs directories when confident"
echo ""
