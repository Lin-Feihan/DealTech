"""Document-level evidence extraction boundary."""

def review(*args, **kwargs):
    return {"status": "Needs Human Review", "note": __doc__}
