CREATE TABLE IF NOT EXISTS page (
  page_name text PRIMARY KEY,
  version_count int NOT NULL,
  version_latest_ptr int,
  recent_view_ts timestamp
);

CREATE TABLE IF NOT EXISTS pages_store (
  page_name text REFERENCES page(page_name) ON DELETE CASCADE ON UPDATE CASCADE,
  version int NOT NULL,
  diff int,
  creation_ts timestamp NOT NULL,
  editor_id text NOT NULL,
  editor_name text NOT NULL,
  content text NOT NULL,
  line_count int NOT NULL,
  delete_status int NOT NULL
);

ALTER TABLE pages_store ADD CONSTRAINT "pages_store_pkey" PRIMARY KEY (page_name, version);
CREATE INDEX pages_store_creation_ts_idx ON pages_store(creation_ts);

CREATE TABLE IF NOT EXISTS inter_page_links (
  id SERIAL PRIMARY KEY,
  page_name_src text REFERENCES page(page_name) ON DELETE CASCADE ON UPDATE CASCADE,
  page_name_dst text
);

CREATE INDEX inter_page_links_src_idx ON inter_page_links(page_name_src);
CREATE INDEX inter_page_links_dst_idx ON inter_page_links(page_name_dst);

CREATE TABLE user_activity (
  id SERIAL PRIMARY KEY,
  user_id text NOT NULL,
  ts timestamp NOT NULL,
  activity_type text NOT NULL,
  page_name text NOT NULL
);

CREATE INDEX user_activity_user_id_idx ON user_activity(user_id);

CREATE TABLE moderator_list (
  mod_name text PRIMARY KEY,
  password_md5 text NOT NULL
);

CREATE TABLE moderator_deletion_logs (
  id SERIAL PRIMARY KEY,
  ts timestamp NOT NULL,
  mod_name text NOT NULL,
  page_name text NOT NULL,
  action text NOT NULL,
  versions text,
  reason text
);

CREATE INDEX moderator_deletion_logs_ts_idx ON moderator_deletion_logs(ts);
