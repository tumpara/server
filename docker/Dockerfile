FROM ubuntu:rolling as build

WORKDIR /usr/src/app
COPY . /usr/src/app/

RUN \
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-pip \
    spatialite-bin libsqlite3-mod-spatialite binutils libproj-dev gdal-bin libexiv2-dev libboost-python-dev && \
  python3 -m pip install -U pip setuptools wheel && \
  python3 -m pip install poetry && \
  # Build the project itself and all the dependencies, so that they can be
  # installed without requiring the system libraries in the next step.
  poetry build && \
  cd dist && \
  python3 -m pip wheel tumpara-*-py3-none-any.whl


FROM ubuntu:rolling

COPY --from=build /usr/src/app/dist/*.whl /usr/src/
# Install libexiv2 and libboost-python by copying the .so files directly. That
# way we can skip a bunch of dependencies we don't need.
COPY --from=build /usr/lib/x86_64-linux-gnu/libboost_python* /usr/lib/x86_64-linux-gnu/libexiv2* /usr/lib/x86_64-linux-gnu/

RUN \
  # Install system packages that are required for some dependencies. These can
  # be looked up on the respective documentation sites for GeoDjango and
  # py3exiv2, see here:
  # - https://docs.djangoproject.com/en/3.2/ref/contrib/gis/install/geolibs/
  # - https://pypi.org/project/py3exiv2/
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3-pip \
    libsqlite3-mod-spatialite proj-bin gdal-bin && \
  python3 -m pip install -U pip setuptools wheel && \
  # Install the server and dependencies globally from the wheels built in the
  # last stage. This will make 'import tumpara' possible from everywhere and
  # makes it a bit easier to adapt the setup using custom Django settings or
  # the like.
  python3 -m pip install /usr/src/*.whl gunicorn && \
  # Setup the working directory for the container (/opt/tumpara). This doesn't
  # contain the app source (since that is installed globally), but rather the
  # setup and other administrative scripts. Additionally, this would be the
  # place to put custom Django settings files.
  mkdir -p /opt/tumpara && \
  mkdir -p /data/static /data/previews && \
  groupadd -g 947 tumpara && \
  useradd -g 947 -u 947 -d /opt/tumpara tumpara && \
  chown -R tumpara:tumpara /data /opt/tumpara && \
  # Symlink the CLI script (which is added later) to 'manage.py', the default
  # for most Django apps. That way we can run commands from the host like this:
  #   docker exec mytumpara ./manage.py sync
  ln -s /opt/tumpara/manage.sh /opt/tumpara/manage.py && \
  # Remove any leftover caches - the first is apt and the second is pip.
  rm -rf /var/lib/apt/lists/* /root/.cache

COPY docker/entrypoint.sh docker/manage.sh docker/tumpara.sh /opt/tumpara/
WORKDIR /opt/tumpara

ENV PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 80

ENTRYPOINT ["/bin/sh", "/opt/tumpara/entrypoint.sh"]
CMD ["/opt/tumpara/tumpara.sh"]
