import fitz  # PyMuPDF
import base64


def pdf_to_page_images(pdf_bytes: bytes, dpi: int = 150) -> list[str]:
    """
    Convert each page of a PDF to a base64-encoded PNG string.
    Returns a list of base64 strings, one per page, in page order.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        png_bytes = pix.tobytes("png")
        images.append(base64.b64encode(png_bytes).decode())
    doc.close()
    return images
