DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS invitation;
DROP TABLE IF EXISTS accepted_invitation;
DROP TABLE IF EXISTS song;
DROP TABLE IF EXISTS user_song;


CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  spotify_id TEXT NOT NULL,
  name TEXT NOT NULL,
  profile_url TEXT NOT NULL,
  photo_url TEXT
);

CREATE TABLE invitation (
  id TEXT PRIMARY KEY NOT NULL,
  author_id INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (author_id) REFERENCES user (id)
);


CREATE TABLE accepted_invitation (
  invitation_id TEXT NOT NULL,
  user_id INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES user (id),
  FOREIGN KEY (invitation_id) REFERENCES invitation (id)
);


CREATE TABLE song (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  artists TEXT NOT NULL,
  duration INTEGER NOT NULL,
  album TEXT,
  year INTEGER,
  hash TEXT NOT NULL
);


CREATE TABLE user_song (
  user_id INTEGER NOT NULL,
  song_id INTEGER NOT NULL,
  source TEXT,
  FOREIGN KEY (user_id) REFERENCES user (id),
  FOREIGN KEY (song_id) REFERENCES song (id)
);