"""
View to serve the React SPA frontend in production.
Uses mimetypes to set correct Content-Type for static assets.
"""
import mimetypes
from django.http import FileResponse, Http404
from django.conf import settings


def serve_react(request, path=''):
    """Serve React build files or index.html for SPA routing."""
    build_dir = settings.REACT_BUILD_DIR

    # Extract path from request if not provided by URL pattern
    if not path:
        path = request.path_info.lstrip('/')

    # If requesting a specific file (JS, CSS, images, etc.)
    if path:
        file_path = build_dir / path
        if file_path.exists() and file_path.is_file():
            content_type, _ = mimetypes.guess_type(str(file_path))
            response = FileResponse(open(file_path, 'rb'), content_type=content_type)
            # Cache static assets for performance
            if any(path.endswith(ext) for ext in ['.js', '.css', '.png', '.jpg', '.svg', '.woff', '.woff2']):
                response['Cache-Control'] = 'public, max-age=31536000, immutable'
            return response

    # For all other routes, serve index.html (SPA)
    index_path = build_dir / 'index.html'
    if index_path.exists():
        return FileResponse(open(index_path, 'rb'), content_type='text/html')

    raise Http404('Frontend not built. Run: cd frontend && npm run build')
