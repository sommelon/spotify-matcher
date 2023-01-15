DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS invitations;
DROP TABLE IF EXISTS accepted_invitations;
DROP TABLE IF EXISTS songs;
DROP TABLE IF EXISTS user_songs;


CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  spotify_id TEXT NOT NULL,
  name TEXT NOT NULL,
  profile_url TEXT NOT NULL,
  photo_url TEXT
);

CREATE TABLE invitations (
  id TEXT PRIMARY KEY NOT NULL,
  author_id INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (author_id) REFERENCES users (id)
);


CREATE TABLE accepted_invitations (
  invitation_id TEXT NOT NULL,
  user_id INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users (id),
  FOREIGN KEY (invitation_id) REFERENCES invitations (id)
);


CREATE TABLE songs (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  artists TEXT NOT NULL,
  url TEXT NOT NULL,
);


CREATE TABLE user_songs (
  user_id INTEGER NOT NULL,
  song_id INTEGER NOT NULL,
  source TEXT,  -- only 'playlist' for now, later may be 'history' and the uniqueness constraint has to be updated, or update the source from history to playlist when the user adds the song to their playlist
  FOREIGN KEY (user_id) REFERENCES users (id),
  FOREIGN KEY (song_id) REFERENCES songs (id),
  UNIQUE (user_id, song_id)
);
