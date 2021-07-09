#!/bin/sh

for gid in $TUMPARA_EXTRA_GROUPS; do
  groupadd "$gid" -g "$gid" >/dev/null 2>&1
  gpasswd -a tumpara "$gid" >/dev/null 2>&1
done

# Explicitly leaving out the quotes around '$*' so we can support commands with
# arguments.
exec runuser -u tumpara -- $*
