#!/bin/sh

bold=$(tput bold)
normal=$(tput sgr0)

echo ""
echo "${bold}[Tumpara]${normal} Running pre-startup actions..."
python -m tumpara migrate --noinput
python -m tumpara collectstatic -c --noinput

echo ""
echo "${bold}[Tumpara]${normal} Starting server processes..."
gunicorn --bind 0.0.0.0:80 tumpara.wsgi
