import os
from pathlib import Path
from datetime import datetime

def setup_media_structure(base_path: str = 'media') -> None:
    """
    Create the required directory structure for media files.
    Media files include: user uploads, order attachments, reports, exports, etc.
    
    Args:
        base_path (str): Base path where the media directory will be created
    """
    current_year = datetime.now().strftime('%Y')
    current_month = datetime.now().strftime('%m')
    
    directories = [
        os.path.join(base_path, current_year, current_month, 'orders', 'attachments'),
        os.path.join(base_path, current_year, current_month, 'orders', 'akt'),
        os.path.join(base_path, current_year, current_month, 'reports'),
        os.path.join(base_path, current_year, current_month, 'exports'),
    ]
    
    for directory in directories:
        try:
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error creating directory {directory}: {e}")
            raise

def setup_static_structure(base_path: str = 'static') -> None:
    """
    Create the required directory structure for static files.
    Static files include: bot guides, tariff images, system files, etc.
    
    Args:
        base_path (str): Base path where the static directory will be created
    """
    directories = [
        os.path.join(base_path, 'images'),
        os.path.join(base_path, 'videos')
    ]
    
    for directory in directories:
        try:
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error creating directory {directory}: {e}")
            raise