CREATE OR REPLACE FUNCTION view_page(in_user_id text, in_page_name text, in_version_gte integer, in_version_lte integer)
RETURNS SETOF pages_store
AS
$$
DECLARE
  v_user_activity_count integer := 0;
BEGIN
  RETURN QUERY SELECT * FROM pages_store WHERE page_name=in_page_name AND version BETWEEN in_version_gte AND in_version_lte AND delete_status=0;
  
  if FOUND THEN
    -- check if user activity log addable
    SELECT COUNT(*) INTO v_user_activity_count FROM user_activity WHERE user_id=in_user_id AND ts > now() - INTERVAL'60s';
    if v_user_activity_count <= 30 THEN
      UPDATE page SET recent_view_ts=now() WHERE page_name=in_page_name;
      INSERT INTO user_activity (user_id, ts, activity_type, page_name)
      VALUES (in_user_id, now(), 'view', in_page_name);
    end if;
  end if;

END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION edit_page(in_user_id text, in_page_name text, in_create integer, in_version_edited integer, in_force integer, in_editor_name text, in_content text, in_line_count integer, in_inter_links text[], OUT out_status integer, OUT out_status_text text )
AS
$$
DECLARE
  v_page_row page%ROWTYPE;
  v_pages_store_row pages_store%ROWTYPE;

  v_count integer := 0;
  v_version_to_set integer := 1;
BEGIN
  -- check if user is ok to post
  SELECT COUNT(*) INTO v_count FROM user_activity WHERE user_id=in_user_id AND activity_type='edit' AND ts > now() - INTERVAL'180s';
  if v_count >= 3 THEN
    out_status = -1;
    out_status_text = 'Please wait for a while before posting.';
    RETURN;
  end if;

  -- check if page is ok to be edited. That is, isn't being edited too much
  SELECT COUNT(*) INTO v_count FROM pages_store WHERE page_name=in_page_name AND creation_ts > now() - INTERVAL'180s';
  if v_count >= 3 THEN
    out_status = -1;
    out_status_text = 'This page was edited multiple times in last few minutes. Please wait before editing.';
    RETURN;
  end if;

  SELECT * INTO v_page_row FROM page WHERE page_name=in_page_name FOR UPDATE;
  
  if FOUND AND in_create = 1 THEN
    out_status = -1;
    out_status_text = 'Page already exists.';
    RETURN;
  end if;  

  if NOT FOUND THEN
    INSERT INTO page (page_name, version_count, version_latest_ptr, recent_view_ts) 
    VALUES (in_page_name, v_version_to_set, v_version_to_set, now() );
  else
    v_version_to_set = v_page_row.version_count + 1;

    -- get row which is current latest version
    SELECT * INTO v_pages_store_row FROM pages_store WHERE page_name=in_page_name AND version=v_page_row.version_latest_ptr;
    if v_pages_store_row.content = in_content THEN
      out_status = -1;
      out_status_text = 'The latest version of the page is the same as your version.';
      RETURN;
    end if;
  end if;

  if in_force = 0 AND in_create = 0 AND in_version_edited < v_version_to_set - 1 THEN
    out_status = -1;
    out_status_text = 'A newer version of the page exists. Use force to push new edit. Careful though.';
    RETURN;
  end if;

  INSERT INTO pages_store (page_name, version, diff, creation_ts, editor_id, editor_name, content, line_count, delete_status )
  VALUES (in_page_name, v_version_to_set, 0, now(), in_user_id, in_editor_name, in_content, in_line_count, 0);

  -- update page now
  UPDATE page SET (version_count, version_latest_ptr, recent_view_ts)=(v_version_to_set, v_version_to_set, now()) WHERE page_name=in_page_name;

  -- add inter links after deleting old
  DELETE FROM inter_page_links WHERE page_name_src=in_page_name;
  -- https://stackoverflow.com/questions/20815028/how-do-i-insert-multiple-values-into-a-postgres-table-at-once
  INSERT INTO inter_page_links (page_name_src, page_name_dst) SELECT in_page_name src, dst FROM unnest(in_inter_links) dst;

  -- add user log
  INSERT INTO user_activity (user_id, ts, activity_type, page_name)
  VALUES (in_user_id, now(), 'edit', in_page_name);

  out_status = v_version_to_set;  
  
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION cleanjob(OUT out_status int)
AS
$$
DECLARE
  v_page_row page%ROWTYPE;
BEGIN


  -- select FOR UPDATE pages which are not viewed in last 180 days and delete EVERYTHING associated with that page
  -- thanks to delete cascade, we need not worry about deleting rows in pages_store and inter_page_links
  DELETE FROM page WHERE recent_view_ts < now() - INTERVAL'100days';

  -- delete old versions 
  DELETE FROM pages_store WHERE creation_ts < now() - INTERVAL'100days' AND NOT EXISTS (SELECT 1 FROM page WHERE page.page_name=pages_store.page_name AND pages_store.version=page.version_latest_ptr);
 
  -- select and delete pages which have no pages_store (delete inter_page_links first)
  DELETE FROM page WHERE NOT EXISTS (SELECT 1 FROM pages_store WHERE page.page_name = pages_store.page_name);

  --FOR v_page_row IN SELECT * FROM page WHERE recent_view_ts < now() - INTERVAL'180days'
  --LOOP
    --DELETE FROM pages_store WHERE page_name=v_page_row.page_name;
    --DELETE FROM inter_page_links WHERE page_name_src=v_page_row.page_name;
    --DELETE FROM page WHERE page_name=v_page_row.page_name;
  --END LOOP;


  -- delete old user activity next ( which are > 10 days )
  DELETE FROM user_activity WHERE ts < now() - INTERVAL'10 days';

  out_status = 1; 
     
END;
$$ LANGUAGE plpgsql;

