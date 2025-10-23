from fastapi import FastAPI, File, UploadFile, HTTPException
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