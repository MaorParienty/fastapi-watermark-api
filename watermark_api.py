from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw, ImageFont
import io
import re
from typing import List
from enum import Enum
import zipfile

app = FastAPI()

# Enum for watermark positions
class WatermarkPosition(str, Enum):
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CENTER = "center"

# Convert hex color to RGBA tuple
def hex_to_rgba(hex_color: str, opacity: int) -> tuple:
    """Convert hex color to RGBA tuple. Defaults to white if invalid."""
    hex_color = hex_color.lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", hex_color):
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (opacity,)
    return (255, 255, 255, opacity)  # Default to white

# Resize image to a maximum resolution
def resize_image(image: Image.Image, max_resolution: int) -> Image.Image:
    """Resize the image to a maximum resolution (e.g., 800x800)."""
    width, height = image.size
    if width > max_resolution or height > max_resolution:
        image.thumbnail((max_resolution, max_resolution))
    return image

# Add watermark to an image
def add_watermark(
    image_data: bytes, 
    text: str, 
    color: str, 
    font_size: int, 
    opacity: int, 
    position: WatermarkPosition, 
    max_resolution: int = None  # Added resolution control
) -> io.BytesIO:
    # Open the image
    try:
        image = Image.open(io.BytesIO(image_data)).convert("RGBA")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    # Resize image if max_resolution is provided
    if max_resolution:
        image = resize_image(image, max_resolution)

    width, height = image.size

    # Convert color
    rgba_color = hex_to_rgba(color, opacity)

    # Create an overlay for the watermark
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Load default font
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    # Get text size
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Calculate position
    if position == WatermarkPosition.TOP_LEFT:
        x, y = 10, 10
    elif position == WatermarkPosition.TOP_RIGHT:
        x, y = width - text_width - 10, 10
    elif position == WatermarkPosition.BOTTOM_LEFT:
        x, y = 10, height - text_height - 10
    elif position == WatermarkPosition.BOTTOM_RIGHT:
        x, y = width - text_width - 10, height - text_height - 10
    elif position == WatermarkPosition.CENTER:
        x, y = width / 2 - text_width / 2, height / 2 - text_height / 2

    # Draw watermark
    draw.text((x, y), text, font=font, fill=rgba_color)

    # Merge watermark with the original image
    watermarked = Image.alpha_composite(image, overlay)

    # Convert back to RGB if needed
    final_image = watermarked.convert("RGB")
    img_io = io.BytesIO()
    final_image.save(img_io, format="JPEG")
    img_io.seek(0)
    return img_io

# Single image watermark endpoint
@app.post("/watermark")
async def watermark_image(
    file: UploadFile = File(...), 
    text: str = "WATERMARK", 
    color: str = "#FFFFFF", 
    font_size: int = 50, 
    opacity: int = 128, 
    position: WatermarkPosition = WatermarkPosition.CENTER, 
    resolution: int = 800  # Default resolution for free users
):
    # Validate opacity
    if opacity < 0 or opacity > 255:
        raise HTTPException(status_code=400, detail="Opacity must be between 0 and 255.")

    # Validate resolution
    if resolution <= 0:
        raise HTTPException(status_code=400, detail="Resolution must be greater than 0.")

    # Read image file
    image_bytes = await file.read()

    # Add watermark
    watermarked_image = add_watermark(
        image_bytes, 
        text, 
        color, 
        font_size, 
        opacity, 
        position, 
        resolution  # Pass resolution to restrict image size
    )

    return StreamingResponse(watermarked_image, media_type="image/jpeg")

# Batch image watermark endpoint
@app.post("/watermark/batch")
async def watermark_batch_images(
    files: List[UploadFile] = File(...),
    text: str = "WATERMARK", 
    color: str = "#FFFFFF", 
    font_size: int = 50, 
    opacity: int = 128, 
    position: WatermarkPosition = WatermarkPosition.CENTER, 
    resolution: int = 800  # Default resolution for free users
):
    # Validate opacity
    if opacity < 0 or opacity > 255:
        raise HTTPException(status_code=400, detail="Opacity must be between 0 and 255.")

    # Validate resolution
    if resolution <= 0:
        raise HTTPException(status_code=400, detail="Resolution must be greater than 0.")

    # Process each image
    watermarked_images = []
    for file in files:
        image_bytes = await file.read()
        watermarked_image = add_watermark(
            image_bytes, 
            text, 
            color, 
            font_size, 
            opacity, 
            position, 
            resolution  # Pass resolution to restrict image size
        )
        watermarked_images.append(watermarked_image)

    # Return a zip file with all watermarked images
    zip_io = io.BytesIO()
    with zipfile.ZipFile(zip_io, "w") as zipf:
        for i, img in enumerate(watermarked_images):
            zipf.writestr(f"watermarked_{i}.jpg", img.getvalue())
    zip_io.seek(0)

    return StreamingResponse(zip_io, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=watermarked_images.zip"})
