# Description

Fetch users songs.

Create invitations.

When an invitation is accepted, fetch the other users songs from their playlists (or history) and keep the info where the song came from.

Find a match.


# Run
## Prerequisites
1. [Install Redis](https://redis.io/docs/getting-started/installation/) and start a new instance.

2. Register a Spotify developer account at [https://developer.spotify.com/dashboard/](https://developer.spotify.com/dashboard/).

   Create an application to receive a client ID and a client secret.

   Add callback URL to the app settings.

   Add users to your app.

3. Create a `.env` file and copy the contents of `env.example`. Update the values.

4. Install dependencies by running `poetry install`.

## Start server
`poetry run flask run`

## Start celery worker
`poetry run python -m celery -A spotify_matcher.flaskr.tasks worker -l info -P solo`
