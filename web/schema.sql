-- Base de datos D1 de la web (valoraciones).
-- Crear:  npx wrangler d1 execute keybio --remote --file=schema.sql

CREATE TABLE IF NOT EXISTS ratings (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  created  TEXT    NOT NULL DEFAULT (datetime('now')),
  stars    INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
  name     TEXT    NOT NULL DEFAULT '' CHECK (length(name) <= 40),
  comment  TEXT    NOT NULL DEFAULT '' CHECK (length(comment) <= 600),
  status   TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  ip_hash  TEXT    NOT NULL   -- HMAC de la IP con IP_SALT: limita a una valoración al día sin guardar la IP
);

CREATE INDEX IF NOT EXISTS ratings_by_ip ON ratings (ip_hash, created);
CREATE INDEX IF NOT EXISTS ratings_by_status ON ratings (status, id);
