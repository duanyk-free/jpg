"""Flask image-tool app — serves the UI and JSON API."""
import argparse
import io
import os
import sys
import tempfile
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_file, abort

from image_engine import (
    load_image,
    image_to_bytes,
    process_resize,
    process_convert,
    process_white_bg,
    process_id_photo,
    get_image_info,
    ID_PHOTO_SIZES,
    RESIZE_PRESETS,
    OUTPUT_FORMATS,
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
)

app = Flask(__name__, static_folder="static", static_url_path="")

# Config
CONFIG = {
    "uploads": {},  # upload_id -> {"path": abs_path, "name": orig_name, ...}
}
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "img_tool_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Store processed results (keyed by result_id)
RESULTS = {}  # result_id -> (bytes, mime_type, filename)


def _save_upload(file_storage) -> dict:
    """Save an uploaded file and return its metadata."""
    if not file_storage or not file_storage.filename:
        abort(400, description="No file provided")

    ext = os.path.splitext(file_storage.filename)[1].lower()
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"}
    if ext not in allowed:
        abort(400, description=f"Unsupported file type: {ext}. Supported: {', '.join(allowed)}")

    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(UPLOAD_DIR, safe_name)
    file_storage.save(dest)

    # Validate it's a real image
    try:
        with open(dest, "rb") as f:
            data = f.read()
        info = get_image_info(data)
    except Exception:
        try:
            os.remove(dest)
        except OSError:
            pass
        abort(422, description="File is not a valid image")

    upload_id = f"upload_{uuid.uuid4().hex[:12]}"
    CONFIG["uploads"][upload_id] = {
        "path": dest,
        "name": file_storage.filename,
        "info": info,
    }
    return {
        "id": upload_id,
        "name": file_storage.filename,
        "info": info,
    }


def _get_upload_data(upload_id: str) -> bytes:
    """Get the raw bytes of an uploaded file."""
    entry = CONFIG["uploads"].get(upload_id)
    if not entry:
        abort(404, description="Upload not found")
    with open(entry["path"], "rb") as f:
        return f.read()


@app.route("/")
def index():
    return send_file("static/index.html")


# ---- API ----

@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload an image file."""
    if "file" not in request.files:
        abort(400, description="No file provided")
    result = _save_upload(request.files["file"])
    return jsonify(result)


@app.route("/api/info/<upload_id>")
def api_info(upload_id):
    """Get image info."""
    data = _get_upload_data(upload_id)
    info = get_image_info(data)
    return jsonify(info)


@app.route("/api/preview/<upload_id>")
def api_preview(upload_id):
    """Return the original image for preview."""
    data = _get_upload_data(upload_id)
    info = get_image_info(data)
    # Return as JPEG for smaller preview
    img = load_image(data)
    preview = image_to_bytes(img, "JPEG", 85)
    return send_file(
        io.BytesIO(preview),
        mimetype="image/jpeg",
    )


@app.route("/api/resize", methods=["POST"])
def api_resize():
    """Resize an image."""
    body = request.get_json(silent=True) or {}
    upload_id = body.get("upload_id")
    if not upload_id:
        abort(400, description="No upload_id provided")

    data = _get_upload_data(upload_id)
    width = body.get("width")
    height = body.get("height")
    keep_aspect = body.get("keep_aspect", True)
    percentage = body.get("percentage")

    try:
        result_bytes, mime, new_w, new_h = process_resize(
            data, width=width, height=height,
            keep_aspect=keep_aspect, percentage=percentage
        )
    except Exception as e:
        abort(500, description=str(e))

    result_id = uuid.uuid4().hex[:12]
    ext = "png" if "png" in mime else "jpg"
    RESULTS[result_id] = (result_bytes, mime, f"resized_{new_w}x{new_h}.{ext}")

    return jsonify({
        "result_id": result_id,
        "width": new_w,
        "height": new_h,
        "size": len(result_bytes),
        "mime": mime,
    })


@app.route("/api/convert", methods=["POST"])
def api_convert():
    """Convert image format."""
    body = request.get_json(silent=True) or {}
    upload_id = body.get("upload_id")
    if not upload_id:
        abort(400, description="No upload_id provided")

    target_format = body.get("format", "PNG")
    # Case-insensitive format lookup
    fmt_lower = target_format.lower()
    fmt_key = None
    for key in OUTPUT_FORMATS:
        if key.lower() == fmt_lower:
            fmt_key = key
            break
    if not fmt_key:
        abort(400, description=f"Unsupported format: {target_format}")

    quality = body.get("quality", 90)

    data = _get_upload_data(upload_id)
    try:
        result_bytes, mime, w, h = process_convert(data, fmt_key, quality)
    except Exception as e:
        abort(500, description=str(e))

    result_id = uuid.uuid4().hex[:12]
    ext = OUTPUT_FORMATS[fmt_key]["ext"]
    entry = CONFIG["uploads"][upload_id]
    base_name = os.path.splitext(entry["name"])[0]
    RESULTS[result_id] = (result_bytes, mime, f"{base_name}.{ext}")

    return jsonify({
        "result_id": result_id,
        "width": w,
        "height": h,
        "size": len(result_bytes),
        "mime": mime,
        "format": fmt_key,
    })


@app.route("/api/white-bg", methods=["POST"])
def api_white_bg():
    """Convert image to white background."""
    body = request.get_json(silent=True) or {}
    upload_id = body.get("upload_id")
    if not upload_id:
        abort(400, description="No upload_id provided")

    model_name = body.get("model") or None

    data = _get_upload_data(upload_id)
    try:
        result_bytes, mime, w, h = process_white_bg(data, model_name=model_name)
    except Exception as e:
        abort(500, description=str(e))

    result_id = uuid.uuid4().hex[:12]
    entry = CONFIG["uploads"][upload_id]
    base_name = os.path.splitext(entry["name"])[0]
    RESULTS[result_id] = (result_bytes, mime, f"{base_name}_白底.jpg")

    return jsonify({
        "result_id": result_id,
        "width": w,
        "height": h,
        "size": len(result_bytes),
        "mime": mime,
    })


@app.route("/api/id-photo", methods=["POST"])
def api_id_photo():
    """Create an ID photo."""
    body = request.get_json(silent=True) or {}
    upload_id = body.get("upload_id")
    if not upload_id:
        abort(400, description="No upload_id provided")

    size_key = body.get("size", "1inch")
    bg_color = body.get("bg_color", "white")
    model_name = body.get("model") or None

    if size_key not in ID_PHOTO_SIZES:
        abort(400, description=f"Unknown ID photo size: {size_key}")

    data = _get_upload_data(upload_id)
    try:
        result_bytes, mime, w, h, label = process_id_photo(
            data, size_key, bg_color, model_name=model_name
        )
    except Exception as e:
        abort(500, description=str(e))

    result_id = uuid.uuid4().hex[:12]
    entry = CONFIG["uploads"][upload_id]
    base_name = os.path.splitext(entry["name"])[0]
    RESULTS[result_id] = (result_bytes, mime, f"{base_name}_{label}.jpg")

    return jsonify({
        "result_id": result_id,
        "width": w,
        "height": h,
        "size": len(result_bytes),
        "mime": mime,
        "label": label,
        "size_key": size_key,
    })


@app.route("/api/download/<result_id>")
def api_download(result_id):
    """Download a processed image."""
    entry = RESULTS.get(result_id)
    if not entry:
        abort(404, description="Result not found")
    data, mime, filename = entry
    return send_file(
        io.BytesIO(data),
        mimetype=mime,
        as_attachment=True,
        download_name=filename,
    )


@app.route("/api/result/<result_id>")
def api_result_preview(result_id):
    """Preview a processed image."""
    entry = RESULTS.get(result_id)
    if not entry:
        abort(404, description="Result not found")
    data, mime, filename = entry
    return send_file(io.BytesIO(data), mimetype=mime)


# ---- Presets ----

@app.route("/api/presets/models")
def api_presets_models():
    """Return available AI models for background removal."""
    return jsonify({
        "models": AVAILABLE_MODELS,
        "default": DEFAULT_MODEL,
    })


@app.route("/api/presets/id-photo")
def api_presets_id_photo():
    """Return ID photo size presets."""
    return jsonify({
        key: {"width": w, "height": h, "label": label}
        for key, (w, h, label) in ID_PHOTO_SIZES.items()
    })


@app.route("/api/presets/resize")
def api_presets_resize():
    """Return resize presets."""
    return jsonify({
        key: {"width": w, "height": h, "label": label}
        for key, (w, h, label) in RESIZE_PRESETS.items()
    })


@app.route("/api/presets/formats")
def api_presets_formats():
    """Return output format info."""
    return jsonify({
        key: {"ext": v["ext"], "mime": v["mime"], "lossless": v["lossless"]}
        for key, v in OUTPUT_FORMATS.items()
    })


# ---- Error handlers ----

@app.errorhandler(404)
def _404(e):
    return jsonify({"error": "not found", "detail": str(e)}), 404


@app.errorhandler(422)
def _422(e):
    return jsonify({"error": "unprocessable", "detail": str(e)}), 422


@app.errorhandler(500)
def _500(e):
    return jsonify({"error": "server error", "detail": str(e)}), 500


def main():
    parser = argparse.ArgumentParser(description="在线图片工具 — resize / convert / ID photo")
    parser.add_argument("--port", type=int, default=8613, help="端口 (默认: 8613)")
    parser.add_argument("--host", default="127.0.0.1", help="绑定地址 (默认: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"🖼️  在线图片工具已启动: {url}")
    print(f"功能: 调整尺寸 | 格式转换 | 白底照片 | 证件照制作")

    if not args.no_browser:
        webbrowser.open(url)

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
