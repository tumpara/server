#!/bin/sh

for gid in $TUMPARA_EXTRA_GROUPS; do
  groupadd "$gid" -g "$gid" >/dev/null
  gpasswd -a tumpara "$gid" >/dev/null
done

# Explicitly leaving out the quotes around '$*' so we can support commands with
# arguments.
exec runuser -u tumpara -- $*
