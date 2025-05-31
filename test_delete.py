import sys
# Add the current directory to sys.path to allow importing app
sys.path.append('.')
try:
    from app import delete_screenshots
    print("Successfully imported delete_screenshots from app.py")
    delete_screenshots('screenshots/')
    print("Finished calling delete_screenshots('screenshots/')")
except ImportError as e:
    print(f"Error importing delete_screenshots: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
