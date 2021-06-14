import io

from tumpara.multimedia.models import ImagePreviewable


class GenericPreviewable(ImagePreviewable):
    def render_preview_image(
        self, width: int, height: int, *args, **kwargs
    ) -> io.BytesIO:
        return io.BytesIO(f"{width}x{height}".encode())
