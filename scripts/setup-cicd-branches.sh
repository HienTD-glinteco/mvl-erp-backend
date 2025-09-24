#!/bin/bash

# Setup script for CI/CD pipeline branches
# This script creates the required branches for the CI/CD pipeline

set -e

echo "🚀 Setting up CI/CD pipeline branches..."

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Current branch: $CURRENT_BRANCH"

# Ensure we're on master branch
if [ "$CURRENT_BRANCH" != "master" ]; then
    echo "⚠️  Switching to master branch..."
    git checkout master
fi

# Pull latest changes
echo "🔄 Pulling latest changes from master..."
git pull origin master

# Create staging branch if it doesn't exist
if git show-ref --verify --quiet refs/heads/staging; then
    echo "✅ staging branch already exists"
else
    echo "🌿 Creating staging branch..."
    git checkout -b staging
    git push origin staging
    git checkout master
    echo "✅ staging branch created and pushed"
fi

# Create release branch if it doesn't exist
if git show-ref --verify --quiet refs/heads/release; then
    echo "✅ release branch already exists"
else
    echo "🌿 Creating release branch..."
    git checkout -b release
    git push origin release
    git checkout master
    echo "✅ release branch created and pushed"
fi

echo ""
echo "🎉 CI/CD pipeline branches setup complete!"
echo ""
echo "📋 Summary of branches:"
git branch -a | grep -E "(master|staging|release)" | head -10

echo ""
echo "📖 Next steps:"
echo "1. Configure GitHub Secrets in repository settings"
echo "2. Set up GitHub Environments (test, staging, production)"
echo "3. Enable deployment methods in workflow files"
echo "4. See docs/GITHUB_SETUP.md for detailed instructions"
echo ""
echo "🚀 Ready to use CI/CD pipeline!"