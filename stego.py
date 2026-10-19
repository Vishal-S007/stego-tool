"""
stego.py — LSB image steganography with optional AES-256 encryption.

Hides a secret message inside the least-significant bits of a PNG's pixels.
Optionally encrypts the payload with a password (PBKDF2 -> AES-256-GCM)
before embedding, so even if the hidden data is extracted it stays unreadable.
"""

import os
import struct
from PIL import Image

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAGIC = b"STG1"          # 4-byte marker so decode knows this is our payload
FLAG_ENCRYPTED = 0x01    # bit set in header when payload is AES-encrypted
SALT_LEN = 16
NONCE_LEN = 12
PBKDF2_ITERS = 200_000


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------
def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERS,
    )
    return kdf.derive(password.encode("utf-8"))


def _encrypt(plaintext: bytes, password: str) -> bytes:
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = _derive_key(password, salt)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return salt + nonce + ct


def _decrypt(blob: bytes, password: str) -> bytes:
    salt = blob[:SALT_LEN]
    nonce = blob[SALT_LEN:SALT_LEN + NONCE_LEN]
    ct = blob[SALT_LEN + NONCE_LEN:]
    key = _derive_key(password, salt)
    return AESGCM(key).decrypt(nonce, ct, None)


# ---------------------------------------------------------------------------
# Payload framing
#   [ MAGIC(4) | flags(1) | length(4, big-endian) | payload(length) ]
# ---------------------------------------------------------------------------
def _build_frame(message: bytes, password: str | None) -> bytes:
    flags = 0
    payload = message
    if password:
        flags |= FLAG_ENCRYPTED
        payload = _encrypt(message, password)
    header = MAGIC + struct.pack("B", flags) + struct.pack(">I", len(payload))
    return header + payload


# ---------------------------------------------------------------------------
# Bit <-> byte conversion
# ---------------------------------------------------------------------------
def _bytes_to_bits(data: bytes):
    for byte in data:
        for i in range(7, -1, -1):
            yield (byte >> i) & 1


def _bits_to_bytes(bits) -> bytes:
    out = bytearray()
    byte = 0
    count = 0
    for bit in bits:
        byte = (byte << 1) | bit
        count += 1
        if count == 8:
            out.append(byte)
            byte = 0
            count = 0
    return bytes(out)


# ---------------------------------------------------------------------------
# Capacity
# ---------------------------------------------------------------------------
def capacity_bytes(img: Image.Image) -> int:
    """Usable payload bytes (3 LSBs per pixel: R, G, B). Minus 9-byte header."""
    w, h = img.size
    total_bits = w * h * 3
    return max(0, total_bits // 8 - 9)


# ---------------------------------------------------------------------------
# Encode
# ---------------------------------------------------------------------------
def encode(in_path: str, out_path: str, message: str, password: str | None = None):
    img = Image.open(in_path).convert("RGB")
    frame = _build_frame(message.encode("utf-8"), password)

    cap = capacity_bytes(img)
    if len(frame) - 9 > cap:
        raise ValueError(
            f"Message too large: need {len(frame)} bytes, image holds {cap + 9}. "
            f"Use a bigger image or a shorter message."
        )

    pixels = list(img.getdata())
    bits = _bytes_to_bits(frame)
    new_pixels = []

    done = False
    for (r, g, b) in pixels:
        if done:
            new_pixels.append((r, g, b))
            continue
        channels = [r, g, b]
        for i in range(3):
            try:
                bit = next(bits)
            except StopIteration:
                done = True
                break
            channels[i] = (channels[i] & ~1) | bit
        new_pixels.append(tuple(channels))

    img.putdata(new_pixels)
    img.save(out_path, "PNG")  # PNG is lossless — required, JPEG would destroy LSBs
    return out_path


# ---------------------------------------------------------------------------
# Decode
# ---------------------------------------------------------------------------
def decode(in_path: str, password: str | None = None) -> str:
    img = Image.open(in_path).convert("RGB")
    pixels = list(img.getdata())

    def lsb_stream():
        for (r, g, b) in pixels:
            yield r & 1
            yield g & 1
            yield b & 1

    stream = lsb_stream()

    def read_bytes(n: int) -> bytes:
        bits = (next(stream) for _ in range(n * 8))
        return _bits_to_bytes(bits)

    if read_bytes(4) != MAGIC:
        raise ValueError("No hidden message found (magic marker missing).")

    flags = read_bytes(1)[0]
    length = struct.unpack(">I", read_bytes(4))[0]

    cap = capacity_bytes(img) + 9
    if length > cap:
        raise ValueError("Corrupt payload (declared length exceeds image).")

    payload = read_bytes(length)

    if flags & FLAG_ENCRYPTED:
        if not password:
            raise ValueError("Payload is encrypted — password required.")
        try:
            payload = _decrypt(payload, password)
        except Exception:
            raise ValueError("Decryption failed — wrong password or corrupt data.")

    return payload.decode("utf-8", errors="replace")
