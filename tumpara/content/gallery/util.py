import PIL.Image


def degrees_to_decimal(value, reference):
    """Convert geographical coordinates to decimal representation.

    :param value: The degrees, as a 3-tuple of 2-tuple rational numbers.
    :param reference: The hemisphere, "N", "E", "S" or "W".
    :raises ValueError: when the input is in an invalid format.
    """
    if len(value) != 3:
        raise ValueError
    try:
        degrees = value[0][0] / value[0][1]
        minutes = value[1][0] / value[1][1]
        seconds = value[2][0] / value[2][1]
    except (KeyError, TypeError):
        raise ValueError
    factor = -1 if reference in ["S", "W"] else 1
    return factor * (degrees + (minutes / 60) + (seconds / 3600))


def correct_pil_image_orientation(image: PIL.Image) -> PIL.Image:
    """Transpose a given image according to the orientation EXIF tag, if required."""
    if "orientation_corrected" in image.info and image.info["orientation_corrected"]:
        return image

    exif = image.getexif()
    if exif and 274 in exif:
        value = exif[274]
        if value == 2:
            image = image.transpose(PIL.Image.FLIP_LEFT_RIGHT)
        elif value == 3:
            image = image.transpose(PIL.Image.ROTATE_180)
        elif value == 4:
            image = image.transpose(PIL.Image.FLIP_TOP_BOTTOM)
        elif value == 5:
            image = image.transpose(PIL.Image.FLIP_LEFT_RIGHT).transpose(
                PIL.Image.ROTATE_90
            )
        elif value == 6:
            image = image.transpose(PIL.Image.ROTATE_270)
        elif value == 7:
            image = image.transpose(PIL.Image.FLIP_TOP_BOTTOM).transpose(
                PIL.Image.ROTATE_90
            )
        elif value == 8:
            image = image.transpose(PIL.Image.ROTATE_90)

    image.info["orientation_corrected"] = True
    return image
