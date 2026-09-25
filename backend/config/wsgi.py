import os

from django.core.wsgi import get_wsgi_application

# Production unless told otherwise: this is what gunicorn, uvicorn and the workers
# load, and falling back to development there meant DEBUG on, any host accepted and
# the mail written to the console. `manage.py` stays on development.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()
