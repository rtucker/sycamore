BROKER_URL = "amqp://guest:guest@localhost:5672//"
CELERY_IMPORTS = ("tasks", )
CELERY_RESULT_BACKEND = "database"
CELERY_RESULT_DBURI = "sqlite:///celerydb.sqlite"
CELERY_TASK_RESULT_EXPIRES = 86400
