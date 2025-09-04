
import io
from PIL import Image
from pyzbar.pyzbar import decode
from pyaadhaar.decode import AadhaarSecureQR

def decode_aadhaar_qr_from_image(image_bytes: bytes) -> dict:
    """
    Decodes an Aadhaar QR code from an image.

    Args:
        image_bytes: The image file in bytes.

    Returns:
        A dictionary containing the decoded Aadhaar data, 
        or an empty dictionary if no valid Aadhaar QR code is found.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        qr_codes = decode(image)

        if not qr_codes:
            return {}

        for qr in qr_codes:
            try:
                qr_data = qr.data.decode("utf-8")
                # Aadhaar QR data is numeric
                if qr_data.isdigit():
                    aadhaar = AadhaarSecureQR(int(qr_data))
                    return aadhaar.decoded_data()
            except (UnicodeDecodeError, ValueError):
                # Continue if the QR code is not valid Aadhaar data
                continue
                
    except Exception as e:
        print(f"An error occurred during Aadhaar QR decoding: {e}")
        
    return {}

