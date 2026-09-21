"""
View to serve the React SPA frontend in production.
"""
from django.http import FileResponse, Http404
from django.conf import settings


def serve_react(request, path=''):
    """Serve React build files or index.html for SPA routing."""
    build_dir = settings.REACT_BUILD_DIR

    # Extract path from request if not provided by URL pattern
    if not path:
        path = request.path_info.lstrip('/')

    # If requesting a specific file (JS, CSS, etc.)
    if path:
        file_path = build_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(open(file_path, 'rb'))

    # For all other routes, serve index.html (SPA)
    index_path = build_dir / 'index.html'
    if index_path.exists():
        return FileResponse(open(index_path, 'rb'))

    raise Http404('Frontend not built. Run: cd frontend && npm run build')
