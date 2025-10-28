from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import StreamingResponse
import rawpy
import io
import os
import tempfile
from PIL import Image, ImageCms

app = FastAPI(title="Raw2JPG Converter Service")

SUPPORTED_EXTS = {'.arw', '.cr2', '.dng', '.nef', '.raw', '.cr3'}

# Convert raw to jpg
@app.post("/convert")
async def convert_raw_to_jpg(file: UploadFile = File(...)):
    # Validate extension
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}")

    # Read raw bytes
    raw_bytes = await file.read()

    # Write to temp file for processing
    try:
        with tempfile.NamedTemporaryFile(suffix=ext) as tmp:
            tmp.write(raw_bytes)
            tmp.flush()
            with rawpy.imread(tmp.name) as raw:
                rgb = raw.postprocess(
                    use_camera_wb=True,
                    no_auto_bright=True,
                    output_color=rawpy.ColorSpace.sRGB,
                    gamma=(2.222, 4.5),
                    bright=1.0,
                    output_bps=8,
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing RAW: {e}")

    # Encode to JPEG in memory with embedded sRGB ICC profile
    try:
        buffer = io.BytesIO()
        img = Image.fromarray(rgb, mode="RGB")
        srgb_profile = ImageCms.createProfile("sRGB")
        icc_bytes = ImageCms.ImageCmsProfile(srgb_profile).tobytes()
        img.save(
            buffer,
            format="JPEG",
            quality=95,
            subsampling=0,
            optimize=True,
            icc_profile=icc_bytes,
        )
        buffer.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error encoding JPEG: {e}")

    # Stream JPEG response
    return StreamingResponse(
        buffer,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f"attachment; filename=\"{os.path.splitext(file.filename)[0]}.jpg\""
        }
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

# ------------------------------------
# New: /watermark endpoint
# ------------------------------------

def _clamp_int(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))

def _apply_opacity(img: Image.Image, opacity_percent: int) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = img.split()[3]
    factor = _clamp_int(opacity_percent, 0, 100) / 100.0
    # Scale alpha channel
    alpha = alpha.point(lambda p: int(p * factor))
    img.putalpha(alpha)
    return img

def _compute_position(base_w: int, base_h: int, wm_w: int, wm_h: int, pos: str, margin: int = 16):
    pos = (pos or "center").lower()
    if pos == "top-left":
        return (margin, margin)
    if pos == "top-right":
        return (max(margin, base_w - wm_w - margin), margin)
    if pos == "bottom-left":
        return (margin, max(margin, base_h - wm_h - margin))
    if pos == "bottom-right":
        return (max(margin, base_w - wm_w - margin), max(margin, base_h - wm_h - margin))
    # center
    return ((base_w - wm_w) // 2, (base_h - wm_h) // 2)

@app.post("/watermark")
async def watermark_image(
    image: UploadFile = File(...),
    watermark: UploadFile = File(...),
    opacity: int = Form(30),
    scalePercent: int = Form(30),
    position: str = Form("center"),
):
    try:
        base_bytes = await image.read()
        wm_bytes = await watermark.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading files: {e}")

    try:
        base_img = Image.open(io.BytesIO(base_bytes)).convert("RGBA")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base image: {e}")

    try:
        wm_img = Image.open(io.BytesIO(wm_bytes)).convert("RGBA")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid watermark image: {e}")

    base_w, base_h = base_img.size
    scale = _clamp_int(scalePercent, 1, 100) / 100.0
    target_w = max(1, int(base_w * scale))
    # keep aspect ratio
    wm_ratio = wm_img.height / wm_img.width
    target_h = max(1, int(target_w * wm_ratio))

    wm_resized = wm_img.resize((target_w, target_h), Image.LANCZOS)
    wm_resized = _apply_opacity(wm_resized, _clamp_int(opacity, 0, 100))

    x, y = _compute_position(base_w, base_h, wm_resized.width, wm_resized.height, position)

    composed = Image.new("RGBA", (base_w, base_h))
    composed.paste(base_img, (0, 0))
    composed.paste(wm_resized, (x, y), wm_resized)

    # Encode to JPEG
    try:
        out_io = io.BytesIO()
        composed.convert("RGB").save(out_io, format="JPEG", quality=90, subsampling=0, optimize=True)
        out_io.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error encoding JPEG: {e}")

    return StreamingResponse(out_io, media_type="image/jpeg")