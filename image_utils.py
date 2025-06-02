from PIL import Image, ImageDraw, ImageFont
import os # For path joining if needed, though not strictly in this function's spec for output_path creation

def gridify_image(image_path, output_path, rows=10, cols=10, label_font_size=12):
    """
    Overlays a grid on an image, labels each cell (e.g., A1, B2), and saves it.

    Args:
        image_path (str): Path to the input image.
        output_path (str): Path to save the gridded image.
        rows (int): Number of rows in the grid.
        cols (int): Number of columns in the grid.
        label_font_size (int): Font size for cell labels.

    Returns:
        str: The output_path if successful, None otherwise.
    """
    try:
        img = Image.open(image_path)
        width, height = img.size
        draw = ImageDraw.Draw(img)

        cell_width = width / cols
        cell_height = height / rows

        # Draw Grid Lines
        for i in range(cols + 1): # Draw cols + 1 vertical lines
            x = i * cell_width
            # Ensure line does not exceed image boundary for the last line if width is not perfectly divisible
            x = min(x, width -1) if i == cols else x 
            draw.line([(x, 0), (x, height)], fill="black")

        for i in range(rows + 1): # Draw rows + 1 horizontal lines
            y = i * cell_height
            # Ensure line does not exceed image boundary for the last line
            y = min(y, height -1) if i == rows else y
            draw.line([(0, y), (width, y)], fill="black")

        # Label Grid Cells
        try:
            font = ImageFont.truetype("arial.ttf", label_font_size)
        except IOError:
            font = ImageFont.load_default() # Fallback to default bitmap font

        for r in range(rows):
            for c in range(cols):
                label = f"{chr(ord('A') + r)}{c + 1}"
                
                # Calculate center of the cell for placing the label
                text_x_center = c * cell_width + cell_width / 2
                text_y_center = r * cell_height + cell_height / 2

                # Get text bounding box using textbbox (Pillow 9.2.0+)
                # The coordinates are (left, top, right, bottom)
                try:
                    bbox = draw.textbbox((0, 0), label, font=font) # (x1, y1, x2, y2)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                except AttributeError: 
                    # Fallback for older Pillow versions that use textsize
                    text_width, text_height = draw.textsize(label, font=font)

                # Calculate top-left position for the text
                text_x = text_x_center - text_width / 2
                text_y = text_y_center - text_height / 2
                
                # Ensure text is drawn within bounds, especially useful for small cells
                # This is a simple clip, more sophisticated handling might be needed for edge cases
                text_x = max(c * cell_width, min(text_x, (c + 1) * cell_width - text_width))
                text_y = max(r * cell_height, min(text_y, (r + 1) * cell_height - text_height))

                draw.text((text_x, text_y), label, fill="red", font=font)

        img.save(output_path)
        return output_path

    except FileNotFoundError:
        print(f"Error: Input image file not found at {image_path}")
        # Consider logging this error instead of print for production code
        return None
    except Exception as e:
        print(f"An error occurred during image processing: {e}")
        # Consider logging this error
        return None

if __name__ == '__main__':
    # Example Usage (optional, for testing the function directly)
    # Create a dummy image for testing
    if not os.path.exists("test_screenshots"):
        os.makedirs("test_screenshots")
    
    try:
        dummy_img = Image.new('RGB', (800, 600), color = 'lightblue')
        dummy_img_path = "test_screenshots/dummy_test_image.png"
        dummy_img.save(dummy_img_path)
        
        print(f"Dummy image saved to {dummy_img_path}")
        
        output_gridded_path = "test_screenshots/gridded_dummy_image.png"
        result_path = gridify_image(dummy_img_path, output_gridded_path, rows=5, cols=5, label_font_size=16)
        
        if result_path:
            print(f"Gridded image saved to: {result_path}")
        else:
            print("Failed to create gridded image.")

    except ImportError:
        print("Pillow library is not installed. This example usage requires Pillow.")
    except Exception as e:
        print(f"An error occurred in example usage: {e}")
