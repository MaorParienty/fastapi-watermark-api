from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw, ImageFont
import io
import re

app = FastAPI()

def hex_to_rgba(hex_color: str, alpha=128) -> tuple:
    """ Convert hex color to RGBA tuple. Defaults to white if invalid. """
    hex_color = hex_color.lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", hex_color):
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)
    return (255, 255, 255, alpha)  # Default to white

def add_x_watermark(image_data: bytes, text: str, color: str, font_size: int) -> io.BytesIO:
    # Open the image
    image = Image.open(io.BytesIO(image_data)).convert("RGBA")
    width, height = image.size

    # Convert color
    rgba_color = hex_to_rgba(color)

    # Create an overlay for the watermark
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Load font
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    # Get text size
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Draw the first diagonal (Top-left to Bottom-right)
    draw.text((10, 10), text, font=font, fill=rgba_color)
    draw.text((width - text_width - 10, height - text_height - 10), text, font=font, fill=rgba_color)

    # Draw the second diagonal (Top-right to Bottom-left)
    draw.text((width - text_width - 10, 10), text, font=font, fill=rgba_color)
    draw.text((10, height - text_height - 10), text, font=font, fill=rgba_color)

    # Centered watermark
    draw.text((width / 2 - text_width / 2, height / 2 - text_height / 2), text, font=font, fill=rgba_color)

    # Merge watermark with the original image
    watermarked = Image.alpha_composite(image, overlay)

    # Convert back to RGB if needed
    final_image = watermarked.convert("RGB")
    img_io = io.BytesIO()
    final_image.save(img_io, format="JPEG")
    img_io.seek(0)
    return img_io

@app.post("/watermark")
async def watermark_image(
    file: UploadFile = File(...), 
    text: str = "WATERMARK", 
    color: str = "#FFFFFF", 
    font_size: int = 50  # Default font size
):
    image_bytes = await file.read()
    watermarked_image = add_x_watermark(image_bytes, text, color, font_size)
    return StreamingResponse(watermarked_image, media_type="image/jpeg")
