#!/bin/bash

echo "BUILD START"

# Install required Python packages
pip install -r requirements.txt

# Collect static files to the correct directory for Vercel
python3.12 manage.py collectstatic --noinput --clear

# Create the expected output directory and copy static files there
mkdir -p staticfiles_build
cp -r staticfiles/* staticfiles_build/ || true

echo "BUILD END"
