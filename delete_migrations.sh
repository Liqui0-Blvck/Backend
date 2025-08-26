#!/bin/bash

# Script to delete all migrations except __init__.py files
# Created for FruitPOS Django project

echo "Starting migration cleanup..."

# Find all migration files (*.py) in migration directories
# Exclude __init__.py files to preserve directory structure
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete

echo "Migration files deleted."
echo "Removing __pycache__ directories in migrations folders..."

# Remove any compiled python files in migrations directories
find . -path "*/migrations/__pycache__" -type d -exec rm -rf {} +

echo "Migration cleanup complete!"
echo "Remember to run 'python manage.py makemigrations' to recreate migrations."
