import os

from celery import Celery
from dotenv import get_key
from flask import Flask

from spotify_matcher.flaskr.invitation import _get_fetched_songs_count


def make_celery(app: Flask):
    celery = Celery(app.import_name)
    celery.conf.update(app.config["CELERY_CONFIG"])

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True, subdomain_matching=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=os.path.join(app.instance_path, "flaskr.sqlite"),
        CELERY_CONFIG={
            "broker_url": "redis://localhost:6379/0",
            "result_backend": "redis://",
            "task_track_started": True,
        },
        SERVER_NAME=get_key(".env", "SERVER_NAME"),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from spotify_matcher.flaskr import db

    db.init_app(app)

    from . import auth

    app.register_blueprint(auth.bp)

    from . import invitation

    app.register_blueprint(invitation.bp)

    app.add_url_rule("/", endpoint="invitation.invitations")

    return app


app = create_app()
celery = make_celery(app)


@app.context_processor
def inject_fetched_songs_count():
    return dict(get_fetched_songs_count=_get_fetched_songs_count)
