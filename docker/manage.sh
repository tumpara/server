#!/bin/sh

# As in entrypoint.sh, we leave out the quotes around '$*' here.
/opt/tumpara/entrypoint.sh python3 -m tumpara $*
