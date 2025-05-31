import pytest
from unittest.mock import MagicMock, patch
from element_detector import ElementDetector # Assuming it's in element_detector.py
import numpy as np # For creating dummy image arrays if needed

# Mock cv2 and YOLO before they are imported by ElementDetector
@pytest.fixture(autouse=True)
def mock_external_libs(mocker):
    # Mock cv2
    cv2_mock = MagicMock()
    cv2_mock.imread.return_value = np.zeros((100, 100, 3), dtype=np.uint8) # Dummy image
    cv2_mock.rectangle = MagicMock()
    cv2_mock.putText = MagicMock()
    cv2_mock.imwrite = MagicMock(return_value=True) # Simulate successful write
    mocker.patch('cv2.imread', cv2_mock.imread)
    mocker.patch('cv2.rectangle', cv2_mock.rectangle)
    mocker.patch('cv2.putText', cv2_mock.putText)
    mocker.patch('cv2.imwrite', cv2_mock.imwrite)

    # Mock YOLO model loading and prediction
    yolo_model_mock = MagicMock()
    # Simulate model prediction: returns a list of result objects,
    # each having a 'boxes' attribute.
    # Each box should have 'xyxy' (coordinates) and 'cls' (class index).
    # And model should have a 'names' attribute for class names.
    mock_box1 = MagicMock()
    mock_box1.xyxy = [[10, 10, 50, 50]] # x1, y1, x2, y2
    mock_box1.cls = [0] # Class index 0

    mock_results = [MagicMock()]
    mock_results[0].boxes = [mock_box1]

    yolo_model_mock.predict.return_value = mock_results
    yolo_model_mock.names = {0: 'button', 1: 'input'} # Example class names

    # Patch the YOLO constructor/loader in element_detector.py
    # This assumes 'YOLO' is imported and used like 'from ultralytics import YOLO'
    # and then 'self.model = YOLO(model_path)'
    # Adjust the patch target string if YOLO is imported differently.
    mocker.patch('element_detector.YOLO', return_value=yolo_model_mock)

    # Mock os.path.exists used for model path checking
    mocker.patch('os.path.exists', return_value=True)


@pytest.fixture
def element_detector_instance(mock_external_libs): # Ensure mocks are active
    # The model_path argument to ElementDetector might need to be a dummy path
    # if os.path.exists is not mocked or if it checks the path before YOLO mock.
    detector = ElementDetector(model_path='dummy_yolov8s.pt')
    return detector

def test_element_detector_initialization(element_detector_instance, mock_external_libs):
    # Check if YOLO was called (mocked constructor)
    from element_detector import YOLO # Import here to get the mocked version
    YOLO.assert_called_once_with('dummy_yolov8s.pt')
    assert element_detector_instance.model is not None

def test_detect_and_annotate_elements(element_detector_instance, mock_external_libs):
    dummy_image_path = 'dummy_image.png'
    mock_browser_automation = MagicMock()

    # Mock get_interactable_elements to return a map compatible with detection
    # The key is the index, value is a mock element with location and size
    mock_selenium_element = MagicMock()
    mock_selenium_element.location = {'x': 10, 'y': 10}
    mock_selenium_element.size = {'width': 40, 'height': 40}

    mock_browser_automation.get_interactable_elements.return_value = {
        1: mock_selenium_element
    }

    # Call the method under test
    output_path = element_detector_instance.detect_and_annotate_elements(
        dummy_image_path,
        mock_browser_automation
    )

    # Assertions
    from cv2 import imread, rectangle, putText, imwrite # Get mocked versions
    imread.assert_called_once_with(dummy_image_path)

    # Check that the model's predict method was called
    element_detector_instance.model.predict.assert_called_once()

    # Check that get_interactable_elements was called
    mock_browser_automation.get_interactable_elements.assert_called_once()

    # Check that cv2.rectangle and cv2.putText were called for the detected element
    # This assumes one element is detected and processed as per the mock setup
    rectangle.assert_called()
    putText.assert_called()

    # Check that cv2.imwrite was called to save the annotated image
    imwrite.assert_called()
    assert output_path.endswith('_annotated.png')

def test_detect_and_annotate_elements_no_image(element_detector_instance, mock_external_libs):
    from cv2 import imread # Get mocked version
    imread.return_value = None # Simulate image loading failure

    dummy_image_path = 'non_existent_image.png'
    mock_browser_automation = MagicMock()

    with pytest.raises(Exception, match="Failed to load image"):
        element_detector_instance.detect_and_annotate_elements(dummy_image_path, mock_browser_automation)

# To run: pytest test_element_detector.py
