FROM python:3 as build

WORKDIR /usr/src/app
COPY . /usr/src/app/

RUN \
  pip install poetry && \
  poetry build


FROM python:3

COPY docker/entrypoint.sh /
COPY --from=build /usr/src/app/dist/tumpara-*-py3-none-any.whl /

RUN \
  apt-get update && \
  pip install -U pip && \
  # Install system dependencies required. These are mostly the ones defined by
  # GeoDjango:
  # https://docs.djangoproject.com/en/3.2/ref/contrib/gis/install/geolibs/
  # We also install the two editors so that the config can be modified from
  # inside the container without too much of a hassle.
  apt-get install -y nano vim spatialite-bin libsqlite3-mod-spatialite binutils libproj-dev gdal-bin && \
  # Install the server globally as a python module. This will make
  # 'import tumpara' possible from everywhere and makes it a bit easier to
  # customize the setup using custom Django settings.
  pip install /tumpara-*-py3-none-any.whl && \
  # We use Gunicorn later to to deploy the WSGI app.
  pip install gunicorn && \
  # Setup the working directory for the container (/opt/tumpara). Since the
  # server is installed globally as module, the app's source code won't live
  # here. Instead, the manage script is placed here and any local settings
  # will be loaded from here (because the directory will be in the Python path).
  # The user ID tumpara runs with is fixed. It's just there so we don't have to
  # use root.
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

COPY docker/manage.sh docker/tumpara.sh /opt/tumpara/

WORKDIR /opt/tumpara

ENV PYTHONUNBUFFERED=1

VOLUME /data
EXPOSE 80

ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
CMD ["/opt/tumpara/tumpara.sh"]
