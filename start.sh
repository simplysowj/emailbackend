#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting SSH service..."
/usr/sbin/sshd &  # Run SSH in the background

echo "Running database migrations..."
python manage.py migrate --noinput  # Prevent interactive prompts

echo "Collecting static files..."
python manage.py collectstatic --noinput  # Avoid user input issues

echo "Starting Django app with Gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 email_automation.wsgi:application
