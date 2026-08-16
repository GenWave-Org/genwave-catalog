"""Byte-level PNG parsing for genwave-catalog's avatar-kind gates (SPEC
F128.1) — signature check, IHDR dimensions, and acTL (APNG) detection, all
BEFORE any image decoder ever touches the bytes. Ported from the app's own
GenWave.Host.Images.PngImageHeader (the same three checks, same chunk-walk
algorithm) so catalog CI enforces the identical shape the app's own upload
pipeline (SPEC F128.6) and its future avatar-pack install re-validation
(SPEC F128.3) already hold — a PNG this module accepts is a PNG the app
would accept too, never the reverse.

Every function is a bounds-checked walk over the raw bytes: a truncated or
malformed chunk sequence returns a firm answer (False, or an explicit
"could not read") rather than raising — a hostile or merely corrupt upload
is exactly the input this module exists to survive, mirroring
PngImageHeader's own "never throws" posture.

Stdlib only (struct.unpack, no Pillow/imaging dependency) — matches this
repo's whole tools/ directory (validate.py's own module docstring: "Stdlib
only").
"""
from __future__ import annotations

import struct

PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


def has_signature(data: bytes) -> bool:
    return data[: len(PNG_SIGNATURE)] == PNG_SIGNATURE


def try_read_dimensions(data: bytes) -> tuple[int, int] | None:
    """Reads width/height straight from the IHDR chunk, which the PNG spec
    requires to be the FIRST chunk immediately after the 8-byte signature —
    never trusts an IHDR-shaped chunk found later in the stream. None on
    anything shorter or differently shaped than that fixed layout (mirrors
    PngImageHeader.TryReadDimensions exactly)."""
    # signature(8) + length(4) + type(4) + width(4) + height(4) = 24 bytes minimum.
    if len(data) < 24 or not has_signature(data):
        return None

    if data[12:16] != b"IHDR":
        return None

    width = struct.unpack(">I", data[16:20])[0]
    height = struct.unpack(">I", data[20:24])[0]
    return width, height


def has_animation_chunk(data: bytes) -> bool:
    """True when an acTL (animation control) chunk appears before the first
    IDAT — the APNG spec's own definition of "this PNG is animated" (SPEC
    F128.1's catalog-CI rule). Walks the chunk stream length-prefixed chunk
    by chunk; a truncated or malformed walk stops and reports False rather
    than raising (mirrors PngImageHeader.HasAnimationChunk exactly, including
    its overflow-shaped/out-of-range length guard)."""
    if not has_signature(data):
        return False

    offset = len(PNG_SIGNATURE)
    total = len(data)
    while offset + 8 <= total:
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]

        if chunk_type == b"acTL":
            return True
        if chunk_type == b"IDAT":
            return False

        # chunk header(8) + data(length) + crc(4) — an overflow-shaped or
        # out-of-range length ends the walk (malformed chunk) instead of
        # wrapping into a negative/runaway advance.
        next_offset = offset + 8 + length + 4
        if next_offset > total:
            return False

        offset = next_offset

    return False
