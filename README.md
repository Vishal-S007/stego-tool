# StegoLab — LSB Image Steganography Tool

Hide encrypted text messages inside images using least-significant-bit (LSB)
steganography, with optional AES-256-GCM encryption. Full-stack: Python/Flask
backend + vanilla JS frontend.

Built for cybersecurity education, CTF practice, and portfolio demonstration.

---

## Features

- **LSB embedding** — writes payload bits into the low bit of each R/G/B channel.
- **AES-256-GCM encryption** (optional) — password → PBKDF2-SHA256 (200k iters)
  → authenticated encryption. Extracted data is unreadable without the password.
- **Capacity check** — UI shows how many bytes an image can hold before you encode.
- **Framed payload** — magic marker + flags + length header, so decode can detect
  whether a hidden message exists and how long it is.
- **Lossless PNG output** — JPEG re-compression would destroy LSBs, so output is
  always PNG.
- **Web UI** — drag-and-drop, live byte counter, encode/decode tabs.

---

## Project layout

```
stego-tool/
├── app.py              Flask backend (routes + upload handling)
├── stego.py            core engine: LSB encode/decode + AES + framing
├── requirements.txt
├── templates/
│   └── index.html      UI
├── static/
│   ├── style.css
│   └── script.js
└── samples/            example cover + stego images (for testing)
```

---

## Run

```bash
cd stego-tool
python3 -m venv venv && source venv/bin/activate      # optional
pip install -r requirements.txt
python3 app.py
```

Open http://127.0.0.1:5000

---

## CLI usage (no server)

```python
import stego

# hide
stego.encode("cover.png", "out.png", "my secret", password="pw")   # password optional

# extract
msg = stego.decode("out.png", password="pw")
print(msg)

# capacity
from PIL import Image
print(stego.capacity_bytes(Image.open("cover.png")), "bytes")
```

---

## How it works

**Embedding.** Each pixel has 3 color channels (R, G, B), each 8 bits. Flipping the
lowest bit changes a value by at most 1 — invisible to the eye. The tool walks the
pixels and overwrites those low bits with the bits of the payload.

**Payload frame.** Before embedding:

```
[ MAGIC "STG1" (4B) | flags (1B) | length (4B, big-endian) | payload (length B) ]
```

On decode, the magic marker confirms a message is present; the length tells the
decoder exactly how many bits to read (no delimiter-scanning needed).

**Encryption.** With a password, the message is encrypted *before* framing:
`salt(16) + nonce(12) + AES-GCM ciphertext`. The `FLAG_ENCRYPTED` bit tells decode
to run decryption. GCM's auth tag also detects tampering / wrong password.

**Capacity.** `width × height × 3 bits ÷ 8 − 9 header bytes`.

---

## Notes & limitations

- Only lossless formats survive. Upload any image; **output is always PNG**.
- This is classic LSB — detectable by steganalysis tools (e.g. chi-square, RS
  analysis, `zsteg`, `StegExpose`). That's expected: understanding detection is
  part of the learning. A natural next phase is adding a steganalysis / detection
  module to the same tool.
- Intended for lawful education, CTF, and research use.

## Possible extensions (portfolio growth)

- Randomized bit placement seeded by the password (harder to detect than sequential).
- Multi-bit LSB (2–3 bits/channel) with a capacity/quality tradeoff slider.
- Embed files, not just text.
- A **steganalysis tab** that flags suspicious images — turns this into both a
  hide *and* detect tool, which reads well to security employers.
