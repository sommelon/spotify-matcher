# Description

Fetch users songs.

Create invitations.

When an invitation is accepted, fetch the other users songs from their playlists (or history) and keep the info where the song came from.

Find a match.


# Run
## Prerequisites
1. [Install Redis](https://redis.io/docs/getting-started/installation/) and start a new instance.

2. Create a `.env` file and copy the contents of `env.example`. Update the values.

Install dependencies by running `poetry install`.

## Start server
`poetry run flask run`

## Start celery worker
`poetry run python -m celery -A spotify_matcher.flaskr.tasks worker -l info -P solo`
