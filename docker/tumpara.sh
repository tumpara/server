#!/bin/sh

bold=$(tput bold)
normal=$(tput sgr0)

echo ""
echo "${bold}[Tumpara]${normal} Running pre-startup actions..."
python3 -m tumpara migrate --noinput
python3 -m tumpara collectstatic -c --noinput

echo ""
echo "${bold}[Tumpara]${normal} Starting server processes..."
python3 -m gunicorn --bind 0.0.0.0:80 tumpara.wsgi
