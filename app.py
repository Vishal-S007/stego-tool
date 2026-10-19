"""
app.py — Flask backend for the LSB steganography tool.

Endpoints
    GET  /              -> serves the web UI
    POST /api/capacity  -> returns usable capacity of an uploaded image
    POST /api/encode    -> hides a message, returns the stego PNG
    POST /api/decode    -> extracts a hidden message
"""

import io
import os
import uuid
import tempfile

from flask import Flask, request, jsonify, send_file, render_template
from PIL import Image

import stego

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB upload cap

ALLOWED = {"png", "bmp", "tiff", "tif", "webp", "jpg", "jpeg"}
TMP = tempfile.gettempdir()


def _ext_ok(name: str) -> bool:
    return "." in name and name.rsplit(".", 1)[1].lower() in ALLOWED


def _save_upload(file_storage) -> str:
    path = os.path.join(TMP, f"stego_{uuid.uuid4().hex}")
    file_storage.save(path)
    return path


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/capacity", methods=["POST"])
def api_capacity():
    f = request.files.get("image")
    if not f or not _ext_ok(f.filename):
        return jsonify({"error": "Provide a valid image file."}), 400
    path = _save_upload(f)
    try:
        img = Image.open(path).convert("RGB")
        cap = stego.capacity_bytes(img)
        return jsonify({"capacity_bytes": cap, "width": img.width, "height": img.height})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        os.remove(path)


@app.route("/api/encode", methods=["POST"])
def api_encode():
    f = request.files.get("image")
    message = request.form.get("message", "")
    password = request.form.get("password") or None

    if not f or not _ext_ok(f.filename):
        return jsonify({"error": "Provide a valid image file."}), 400
    if not message:
        return jsonify({"error": "Message is empty."}), 400

    in_path = _save_upload(f)
    out_path = os.path.join(TMP, f"stego_out_{uuid.uuid4().hex}.png")
    try:
        stego.encode(in_path, out_path, message, password)
        return send_file(
            out_path,
            mimetype="image/png",
            as_attachment=True,
            download_name="stego.png",
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Encode failed: {e}"}), 500
    finally:
        os.remove(in_path)
        # out_path removed after send on most setups; clean if it lingers
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass


@app.route("/api/decode", methods=["POST"])
def api_decode():
    f = request.files.get("image")
    password = request.form.get("password") or None

    if not f or not _ext_ok(f.filename):
        return jsonify({"error": "Provide a valid image file."}), 400

    path = _save_upload(f)
    try:
        msg = stego.decode(path, password)
        return jsonify({"message": msg})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Decode failed: {e}"}), 500
    finally:
        os.remove(path)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
