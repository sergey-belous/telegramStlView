/** Общие настройки CouchDB (браузер → хост :5984). См. docker-compose, сервис couchdb. */

export const COUCHDB_URL =
  import.meta.env.VITE_COUCHDB_URL ?? 'http://localhost:5984';

export const COUCHDB_DATABASE =
  import.meta.env.VITE_COUCHDB_DATABASE ?? 'telegram_messages_2';

export const COUCHDB_AUTH = {
  username: import.meta.env.VITE_COUCHDB_USER ?? 'admin',
  password: import.meta.env.VITE_COUCHDB_PASSWORD ?? 'password',
} as const;

export function couchdbAllDocsUrl(): string {
  return `${COUCHDB_URL}/${encodeURIComponent(COUCHDB_DATABASE)}/_all_docs?include_docs=true`;
}
