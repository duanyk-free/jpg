"""Image processing engine — resize, convert, white background, ID photos."""
import io
from PIL import Image, ImageFilter

# Supported AI models for background removal
# u2net_human_seg: optimized for human segmentation (~170MB, recommended)
# u2net: general purpose, faster (~176MB)
# birefnet-portrait: highest quality for portraits (~973MB, slow download)
AVAILABLE_MODELS = {
    "u2net_human_seg": "U2Net 人像 (推荐)",
    "u2net": "U2Net 通用 (快速)",
    "birefnet-portrait": "BiRefNet 人像 (最高质量, 大模型)",
}
DEFAULT_MODEL = "u2net_human_seg"

# Lazy-loaded rembg sessions (one per model)
_rembg_sessions = {}


def _get_rembg_session(model_name: str = None):
    """Get or create a rembg session (lazy init, cached per model)."""
    if model_name is None:
        model_name = DEFAULT_MODEL
    if model_name not in AVAILABLE_MODELS:
        model_name = DEFAULT_MODEL

    if model_name not in _rembg_sessions:
        from rembg import new_session
        _rembg_sessions[model_name] = new_session(model_name)
    return _rembg_sessions[model_name]


def remove_background(data: bytes, model_name: str = None) -> Image.Image:
    """Remove background from an image using AI (rembg).

    Uses alpha_matting for sharp edges and post_process_mask for smooth results.

    Returns an RGBA PIL Image with transparent background.
    For images that already have transparency, returns as-is.
    """
    img = load_image(data)

    # If image already has an alpha channel, use it directly
    if img.mode == "RGBA":
        return img
    if img.mode == "LA":
        return img.convert("RGBA")

    # Use rembg for AI background removal with edge refinement
    from rembg import remove
    session = _get_rembg_session(model_name)

    img_rgba = remove(
        img,
        session=session,
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=10,
        post_process_mask=True,
    )
    return img_rgba


def _composite_on_color(img: Image.Image, color: tuple) -> Image.Image:
    """Composite an RGBA image onto a solid color background. Returns RGB."""
    if img.mode in ("LA", "P"):
        img = img.convert("RGBA")
    background = Image.new("RGB", img.size, color)
    if img.mode == "RGBA":
        background.paste(img, mask=img.split()[3])
    else:
        background.paste(img)
    return background


# ID photo presets (at 300 DPI)
# Size name -> (width_px, height_px, label_cn)
ID_PHOTO_SIZES = {
    "1inch": (295, 413, "一寸 (25×35mm)"),
    "2inch": (413, 579, "二寸 (35×49mm)"),
    "small1inch": (260, 378, "小一寸 (22×32mm)"),
    "small2inch": (413, 531, "小二寸 (35×45mm)"),
    "large1inch": (295, 413, "大一寸 (25×35mm)"),
    "large2inch": (413, 626, "大二寸 (35×53mm)"),
}

# Common resize presets
RESIZE_PRESETS = {
    "800x600": (800, 600, "800×600"),
    "1024x768": (1024, 768, "1024×768"),
    "1280x720": (1280, 720, "1280×720 (HD)"),
    "1920x1080": (1920, 1080, "1920×1080 (Full HD)"),
    "640x640": (640, 640, "640×640 (正方形)"),
    "1080x1080": (1080, 1080, "1080×1080 (Instagram)"),
}

# Supported output formats
OUTPUT_FORMATS = {
    "PNG": {"ext": "png", "mime": "image/png", "lossless": True},
    "JPEG": {"ext": "jpg", "mime": "image/jpeg", "lossless": False},
    "JPG": {"ext": "jpg", "mime": "image/jpeg", "lossless": False},
    "WebP": {"ext": "webp", "mime": "image/webp", "lossless": False},
    "BMP": {"ext": "bmp", "mime": "image/bmp", "lossless": True},
}

# ID photo background colors
BG_COLORS = {
    "white": (255, 255, 255),
    "red": (200, 22, 30),      # Standard ID photo red
    "blue": (60, 120, 210),    # Standard ID photo blue
}


def load_image(data: bytes) -> Image.Image:
    """Load an image from bytes, handle EXIF orientation."""
    img = Image.open(io.BytesIO(data))
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img


def image_to_bytes(img: Image.Image, fmt: str = "PNG", quality: int = 95) -> bytes:
    """Convert PIL Image to bytes in the given format."""
    buf = io.BytesIO()
    save_format = fmt.upper()
    if save_format == "JPG":
        save_format = "JPEG"

    # Ensure image is in a mode supported by the output format
    if save_format in ("JPEG", "BMP"):
        if img.mode in ("RGBA", "LA", "P"):
            # Convert transparent images to white background for JPEG/BMP
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
    elif save_format == "WebP":
        if img.mode not in ("RGB", "RGBA"):
            if img.mode in ("LA", "P"):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")

    save_kwargs = {"format": save_format}
    if save_format == "JPEG":
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    elif save_format == "WebP":
        save_kwargs["quality"] = quality
    elif save_format == "PNG":
        save_kwargs["optimize"] = True

    img.save(buf, **save_kwargs)
    return buf.getvalue()


def process_resize(data: bytes, width: int = None, height: int = None,
                   keep_aspect: bool = True, percentage: int = None) -> tuple:
    """Resize an image.

    Returns (image_bytes, mime_type, new_width, new_height).
    """
    img = load_image(data)
    orig_w, orig_h = img.size

    if percentage and percentage != 100:
        new_w = int(orig_w * percentage / 100)
        new_h = int(orig_h * percentage / 100)
    elif width and height:
        if keep_aspect:
            img.thumbnail((width, height), Image.LANCZOS)
            new_w, new_h = img.size
        else:
            new_w, new_h = width, height
            img = img.resize((new_w, new_h), Image.LANCZOS)
    elif width:
        ratio = width / orig_w
        new_w, new_h = width, int(orig_h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    elif height:
        ratio = height / orig_h
        new_w, new_h = int(orig_w * ratio), height
        img = img.resize((new_w, new_h), Image.LANCZOS)
    else:
        new_w, new_h = orig_w, orig_h

    fmt = "PNG" if img.mode in ("RGBA", "LA", "P") else "JPEG"
    out = image_to_bytes(img, fmt)
    mime = OUTPUT_FORMATS[fmt]["mime"] if fmt in OUTPUT_FORMATS else "image/png"
    if fmt == "JPEG":
        mime = "image/jpeg"
    elif fmt == "PNG":
        mime = "image/png"
    return out, mime, new_w, new_h


def process_convert(data: bytes, target_format: str, quality: int = 90) -> tuple:
    """Convert image to a different format.

    Returns (image_bytes, mime_type, width, height).
    """
    img = load_image(data)
    orig_w, orig_h = img.size
    fmt_info = OUTPUT_FORMATS.get(target_format, OUTPUT_FORMATS["PNG"])
    out = image_to_bytes(img, target_format, quality)
    return out, fmt_info["mime"], orig_w, orig_h


def process_white_bg(data: bytes, model_name: str = None) -> tuple:
    """Remove background and fill with white using AI background removal.

    Uses alpha_matting for sharp, non-blurry edges.

    Returns (image_bytes, mime_type, width, height).
    """
    img = load_image(data)
    orig_w, orig_h = img.size

    # AI background removal with edge refinement
    img_rgba = remove_background(data, model_name=model_name)

    # Composite onto white background
    img = _composite_on_color(img_rgba, (255, 255, 255))

    out = image_to_bytes(img, "JPEG", 100)
    return out, "image/jpeg", orig_w, orig_h


def process_id_photo(data: bytes, size_key: str = "1inch",
                     bg_color: str = "white",
                     model_name: str = None) -> tuple:
    """Create an ID photo with AI background removal.

    Optimized pipeline for sharp results:
    1. Center-crop to target aspect ratio FIRST (AI focuses on the person)
    2. Remove background with AI + alpha matting
    3. Resize to exact ID photo dimensions
    4. Fill background with the chosen color

    Args:
        data: Original image bytes.
        size_key: One of ID_PHOTO_SIZES keys.
        bg_color: 'white', 'red', or 'blue'.
        model_name: One of AVAILABLE_MODELS keys, or None for default.

    Returns (image_bytes, mime_type, width, height, size_label).
    """
    if size_key not in ID_PHOTO_SIZES:
        size_key = "1inch"

    target_w, target_h, label = ID_PHOTO_SIZES[size_key]
    bg_rgb = BG_COLORS.get(bg_color, (255, 255, 255))

    img = load_image(data)
    orig_w, orig_h = img.size

    # Step 1: Center-crop to target aspect ratio BEFORE background removal
    # This lets the AI focus on the person, not the surroundings
    target_ratio = target_w / target_h
    orig_ratio = orig_w / orig_h

    if orig_ratio > target_ratio:
        new_w = int(orig_h * target_ratio)
        left = (orig_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, orig_h))
    elif orig_ratio < target_ratio:
        new_h = int(orig_w / target_ratio)
        top = (orig_h - new_h) // 2
        img = img.crop((0, top, orig_w, top + new_h))

    # Step 2: Remove background with AI (on the cropped image for better focus)
    # Convert cropped image to bytes for remove_background
    buf = io.BytesIO()
    save_fmt = "PNG"
    img.save(buf, format=save_fmt)
    cropped_data = buf.getvalue()

    img_rgba = remove_background(cropped_data, model_name=model_name)

    # Step 3: Resize to exact ID photo dimensions
    img_rgba = img_rgba.resize((target_w, target_h), Image.LANCZOS)

    # Step 4: Composite onto colored background
    img = _composite_on_color(img_rgba, bg_rgb)

    out = image_to_bytes(img, "JPEG", 100)
    return out, "image/jpeg", target_w, target_h, label


def get_image_info(data: bytes) -> dict:
    """Get basic info about an image."""
    img = Image.open(io.BytesIO(data))
    fmt = img.format or "Unknown"
    mode = img.mode
    w, h = img.size
    file_size = len(data)
    has_alpha = mode in ("RGBA", "LA") or (mode == "P" and "transparency" in img.info)
    return {
        "format": fmt,
        "mode": mode,
        "width": w,
        "height": h,
        "file_size": file_size,
        "has_alpha": has_alpha,
    }
