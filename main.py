from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
import rawpy
import imageio
import io
import os
import tempfile

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
                rgb = raw.postprocess()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing RAW: {e}")

    # Encode to JPEG in memory
    try:
        buffer = io.BytesIO()
        imageio.imwrite(buffer, rgb, format='JPEG')
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