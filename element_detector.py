import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
from selenium.webdriver.common.by import By

class ElementDetector:
    def __init__(self):
        self.font_size = 16
        self.circle_radius = 12
        self.circle_color = (255, 0, 0)  # Red
        self.text_color = (255, 255, 255)  # White
        
    def detect_and_annotate_elements(self, screenshot_path, browser_automation=None):
        """Detect interactive elements and annotate them with indexes"""
        try:
            # Load the screenshot
            image = Image.open(screenshot_path)
            
            # Create a copy for annotation
            annotated_image = image.copy()
            draw = ImageDraw.Draw(annotated_image)
            
            # Try to load a font, fallback to default if not available
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", self.font_size)
            except:
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", self.font_size)
                except:
                    font = ImageFont.load_default()
            
            # Get element positions from browser if provided
            positions = {}
            if browser_automation:
                positions = self.get_element_positions_from_browser(browser_automation)
            
            # Annotate each element
            for index, (x, y, width, height) in positions.items():
                # Calculate center position
                center_x = x + width // 2
                center_y = y + height // 2
                
                # Draw red circle
                circle_bbox = [
                    center_x - self.circle_radius,
                    center_y - self.circle_radius,
                    center_x + self.circle_radius,
                    center_y + self.circle_radius
                ]
                draw.ellipse(circle_bbox, fill=self.circle_color, outline=self.circle_color)
                
                # Draw index number in white
                text = str(index)
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                text_x = center_x - text_width // 2
                text_y = center_y - text_height // 2
                
                draw.text((text_x, text_y), text, fill=self.text_color, font=font)
            
            # Save the annotated image
            base_name = os.path.splitext(screenshot_path)[0]
            annotated_path = f"{base_name}_annotated.png"
            annotated_image.save(annotated_path)
            
            return annotated_path
            
        except Exception as e:
            print(f"Error in element detection: {str(e)}")
            return screenshot_path  # Return original if annotation fails
    
    def annotate_elements_with_positions(self, screenshot_path, element_positions):
        """Annotate elements given their positions"""
        try:
            # Load the screenshot
            image = Image.open(screenshot_path)
            annotated_image = image.copy()
            draw = ImageDraw.Draw(annotated_image)
            
            # Try to load a font
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", self.font_size)
            except:
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", self.font_size)
                except:
                    font = ImageFont.load_default()
            
            # Annotate each element
            for index, (x, y, width, height) in element_positions.items():
                # Calculate center position
                center_x = x + width // 2
                center_y = y + height // 2
                
                # Draw red circle
                circle_bbox = [
                    center_x - self.circle_radius,
                    center_y - self.circle_radius,
                    center_x + self.circle_radius,
                    center_y + self.circle_radius
                ]
                draw.ellipse(circle_bbox, fill=self.circle_color, outline=self.circle_color)
                
                # Draw index number in white
                text = str(index)
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                text_x = center_x - text_width // 2
                text_y = center_y - text_height // 2
                
                draw.text((text_x, text_y), text, fill=self.text_color, font=font)
            
            # Save annotated image
            base_name = os.path.splitext(screenshot_path)[0]
            annotated_path = f"{base_name}_annotated.png"
            annotated_image.save(annotated_path)
            
            return annotated_path
            
        except Exception as e:
            print(f"Error in element annotation: {str(e)}")
            return screenshot_path
    
    def get_element_positions_from_browser(self, browser_automation):
        """Extract element positions from browser automation instance"""
        if not browser_automation or not browser_automation.driver:
            return {}
        
        try:
            # Get interactable elements
            element_map = browser_automation.get_interactable_elements()
            
            positions = {}
            for index, element in element_map.items():
                try:
                    location = element.location
                    size = element.size
                    
                    positions[index] = (
                        location['x'],
                        location['y'],
                        size['width'],
                        size['height']
                    )
                except:
                    continue
            
            return positions
            
        except Exception as e:
            print(f"Error getting element positions: {str(e)}")
            return {}
    
    def create_annotated_screenshot(self, browser_automation):
        """Take screenshot and annotate with element indexes"""
        try:
            if not browser_automation:
                raise Exception("Browser automation instance required")
            
            # Take screenshot
            screenshot_path = browser_automation.take_screenshot()
            
            # Get element positions
            positions = self.get_element_positions_from_browser(browser_automation)
            
            if not positions:
                print("No elements detected for annotation")
                return screenshot_path
            
            # Annotate with positions
            annotated_path = self.annotate_elements_with_positions(screenshot_path, positions)
            
            return annotated_path
            
        except Exception as e:
            print(f"Error creating annotated screenshot: {str(e)}")
            return None
