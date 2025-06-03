import pytesseract
from PIL import Image
import os

def extract_text_from_image(image_path: str) -> str:
    """
    Extracts text from an image using Tesseract OCR.

    Args:
        image_path: Path to the image file.

    Returns:
        The extracted text as a string, or a specific error string if Tesseract is not found,
        or an empty string for other errors or no text.
    """
    try:
        if not os.path.exists(image_path):
            # print(f"OCR Error: Image path does not exist: {image_path}")
            return ""

        # Note: The logic for finding tesseract_cmd has been removed as it's highly
        # environment-specific and often better handled by ensuring Tesseract
        # is correctly installed and in PATH, or configured once globally if needed.
        # If TesseractNotFoundError occurs, it indicates a setup issue.

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except FileNotFoundError:
        # print(f"OCR Error: Image file not found at {image_path}.")
        return ""
    except pytesseract.TesseractNotFoundError:
        # This error is raised if the Tesseract executable isn't found.
        # print("OCR Error: Tesseract is not installed or not in your PATH. Please install Tesseract OCR engine.")
        return "OCR_ERROR_TESSERACT_NOT_FOUND" # Special string to indicate this specific issue
    except Exception as e:
        # print(f"OCR Error: An unexpected error occurred during OCR: {e}")
        return ""

if __name__ == '__main__':
    # This part is for testing the script directly.
    # Its full functionality in a sandboxed environment might be limited
    # by availability of image files, fonts, or a Tesseract installation.
    print("ocr_utils.py loaded. To test, call extract_text_from_image('path/to/your/image.png')")

    # Attempt to create and test with a dummy image
    dummy_image_created = False
    try:
        from PIL import Image, ImageDraw, ImageFont
        if not os.path.exists("dummy_ocr_test.png"):
            img = Image.new('RGB', (600, 150), color = (220, 220, 220))
            d = ImageDraw.Draw(img)
            try:
                # Try a common system font, otherwise default.
                # This path might not exist in all environments.
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if not os.path.exists(font_path):
                    font_path = "arial.ttf" # Common on Windows, might exist elsewhere
                font = ImageFont.truetype(font_path, 30)
            except IOError:
                # print("Test warning: Specific font not found, using default.")
                font = ImageFont.load_default()

            d.text((20,20), "Hello World from OCR Test\nLine 2 example text\n12345 !@#$%", fill=(0,0,0), font=font)
            img.save("dummy_ocr_test.png")
            dummy_image_created = True
            print("Created dummy_ocr_test.png for testing.")

        if dummy_image_created:
            print("\n--- Running OCR Test ---")
            text_content = extract_text_from_image("dummy_ocr_test.png")
            print(f"Extracted text: '{text_content}'")

            if text_content == "OCR_ERROR_TESSERACT_NOT_FOUND":
                print("OCR Test Result: FAILED - Tesseract executable not found. Please install Tesseract OCR and ensure it's in your system's PATH.")
            elif "Hello World" in text_content and "Line 2" in text_content:
                print("OCR Test Result: SUCCESS - Basic text extraction seems to be working.")
            elif not text_content:
                print("OCR Test Result: No text extracted. This could be due to various reasons (e.g., Tesseract issues not caught as TesseractNotFoundError, image too complex, or actual empty extraction).")
            else:
                print("OCR Test Result: Partial or unexpected text extracted. Review output.")

            # Clean up dummy image
            # os.remove("dummy_ocr_test.png")
            # print("Cleaned up dummy_ocr_test.png")

    except ImportError:
        print("Test warning: Pillow's ImageDraw or ImageFont could not be imported. Cannot create dummy image for full self-test.")
    except Exception as e:
        print(f"Error during OCR self-test setup or execution: {e}")
