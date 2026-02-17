
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import QByteArray, QSize

def get_icon(name: str, color: str = "#e0e0e0") -> QIcon:
    """Generates a QIcon from an internal SVG path."""
    
    # Material Design style icons
    # Viewport 0 0 24 24
    
    # Simple SVG template
    paths = {
        "play": f"""<path d="M8 5v14l11-7z" fill="{color}"/>""",
        "stop": f"""<path d="M6 6h12v12H6z" fill="{color}"/>""",
        "folder": f"""<path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z" fill="{color}"/>""",
        "zoom_in": f"""
            <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" fill="{color}"/>
            <path d="M12 10h-2v2H9v-2H7V9h2V7h1v2h2v1z" fill="{color}"/>
        """,
        "zoom_out": f"""
            <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14zM7 9h5v1H7z" fill="{color}"/>
        """,
        "reset": f"""<path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" fill="{color}"/>""",
        "record": f"""<path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" fill="{color}"/><path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" fill="{color}"/>""",
        "practice": f"""<path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" fill="{color}"/>""",
        "rec_on": f"""<circle cx="12" cy="12" r="8" fill="#ff4444"/>""",
        "rec_off": f"""<circle cx="12" cy="12" r="8" fill="{color}"/>""",
    }

    content = paths.get(name, "")
    full_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">{content}</svg>"""
    
    # Load SVG data into pixmap
    img_data = QByteArray(full_svg.encode('utf-8'))
    pixmap = QPixmap()
    pixmap.loadFromData(img_data)
    
    return QIcon(pixmap)
