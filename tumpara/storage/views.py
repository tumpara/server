from django.core import signing
from django.http import Http404
from django.views.static import serve

from .backends import FileSystemBackend
from .models import File


def file_download(request, primary_key):
    """Serve a File object's actual raw file.

    :param primary_key: The signed primary key of the file object.
    """
    try:
        # URLs go invalid after an hour
        actual_primary_key = signing.loads(primary_key, max_age=3600)
        file_obj = File.objects.select_related("library").get(
            pk=actual_primary_key, orphaned=False
        )
    except (
        signing.BadSignature,
        signing.SignatureExpired,
        ValueError,
        File.DoesNotExist,
    ):
        raise Http404()

    if isinstance(file_obj.library.backend, FileSystemBackend):
        # For file system backends, we can serve the file as is, without needing to open
        # it here directly.
        # TODO Use some sort of sendfile-like serving mechanism. See here:
        #  https://github.com/johnsensible/django-sendfile/blob/master/sendfile/backends/nginx.py
        return serve(request, file_obj.path, file_obj.library.backend.base_location)
    else:
        # TODO Implement this. We probably need to redo the serve() function from above
        #   entirely because we want to support If-Modified-Since headers, content types
        #   and so on.
        raise NotImplementedError(
            "File downloads are not implemented yet for backends other than the "
            "filesystem backend."
        )
