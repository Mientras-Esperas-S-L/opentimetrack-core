__version__ = "0.1.0"


def __getattr__(name):
    """`celery -A config` busca `config.celery_app`. Se importa solo cuando lo
    piden: un despliegue con cron no tiene por qué cargar Celery al arrancar
    Django, y hasta hoy `config/celery.py` ni existía --- el servicio `worker`
    del compose apuntaba a un módulo que no estaba."""
    if name == "celery_app":
        from config.celery import app

        return app
    raise AttributeError(name)
