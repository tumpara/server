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
