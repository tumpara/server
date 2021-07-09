#!/bin/sh

# As in entrypoint.sh, we leave out the quotes around '$*' here.
/entrypoint.sh python -m tumpara $*
