
import psycopg2
import psycopg2.extensions
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

import time
from datetime import datetime
import re

from app import app


from flask import render_template, jsonify, request, redirect, url_for
import base64, hashlib

class Handler:
    def __init__(self) :
        self.con = psycopg2.connect("dbname='anonswiki_db' user='anonswiki_role'")

    def __del__(self) :
        if self.con :
            self.con.close()

    def view_page(self, page_name) :
        user_id = Handler.userId()
        version = 0 #0 means latest version get

        if len(page_name) > 64 :
            return Handler.render_page_simple('404 : page name too long'), 404 
        if not re.match('^[\w\d_]+$', page_name) :
            return Handler.render_page_simple('404 : page name contains unsupported characters'), 404 

        if 'v' in request.args :
            if Handler.representsInt(request.args['v']) :
                version = int(request.args['v'])

        cur = self.con.cursor()
        
        cur.execute("SELECT * FROM page WHERE page_name=%s", (page_name,) )

        res = cur.fetchall()        

        if not res :
            return Handler.render_page_simple('404 : page not found'), 404

        page_row = res[0]
        version_count = page_row[1]
        version_latest = page_row[2]
        recent_view_datetime = page_row[3]

        if version <= 0 :
            version = version + version_latest


        cur.execute("SELECT * FROM view_page(%s, %s, %s, %s)", 
                (user_id, page_name, version, version) )
        res = cur.fetchall()

        self.con.commit()

        if not res :
            return Handler.render_page_simple('404 : version not found'), 404
        pages_store_row = res[0]
        

        page_version = pages_store_row[1]
        diff = pages_store_row[2]
        creation_ts_datetime = pages_store_row[3]
        editor_name = Handler.tripcode_name(pages_store_row[5])
        page_content = pages_store_row[6]

        line_count = pages_store_row[7]

        version_text = '{}{}'.format(page_version, ' (latest)' if page_version==version_latest else '')
        
        content = Handler.renderContent(page_content)
               
        page = {
            'page_name' : page_name,
            'created_before' : Handler.getAgeFromDatetime(creation_ts_datetime),
            'view_before' : Handler.getAgeFromDatetime(recent_view_datetime),
            'version' : page_version,
            'version_text' : version_text,
            'content' : content,
            'editor_name' : editor_name,

            'line_count' : line_count
        }

        return render_template('view_page.html', page=page)

    def version_history(self, page_name) :
        if len(page_name) > 64 :
            return Handler.render_page_simple('404 : page name too long'), 404 
        if not re.match('^[\w\d_]+$', page_name) :
            return Handler.render_page_simple('404 : page name contains unsupported characters'), 404 

        cur = self.con.cursor()

        cur.execute("SELECT * FROM pages_store WHERE page_name=%s AND delete_status=0 ORDER BY version DESC LIMIT 1000", (page_name,) )

        res = cur.fetchall()

        if not res :
            return Handler.render_page_simple('404 : nothing found'), 404 

        html_lines = []

        for row in res :
            version = row[1]
            creation_ts = row[3]
            editor_name = Handler.tripcode_name(row[5])

            creation_date_age = Handler.getAgeFromDatetime(creation_ts)

            line = u"<a href='/{}/?v={}'>v{}</a> created {} ago by {}".format(page_name, version, version, creation_date_age, editor_name)

            html_lines.append(line)

        version_history_lines = '<br><br>'.join(html_lines)

        page = {
            'page_name' : page_name,
            'version_history_lines' : version_history_lines
        }

        return render_template('version_history.html', page=page)

    def recent_edits(self) :
        cur = self.con.cursor()

        cur.execute("SELECT * FROM pages_store ORDER BY creation_ts DESC LIMIT 1000")

        res = cur.fetchall()

        html_lines = []

        for row in res :
            page_name = row[0]
            version = row[1]
            creation_ts = row[3]
            editor_name = Handler.tripcode_name(row[5])

            creation_date_age = Handler.getAgeFromDatetime(creation_ts)

            line = u"<a href='/{}/?v={}'>{} v{}</a> created {} ago by {}".format(page_name, version, page_name,  version, 
                    creation_date_age, editor_name)

            html_lines.append(line)

        recent_edits_lines = '<br><br>'.join(html_lines)

        page = {
            'recent_edits_lines' : recent_edits_lines
        }

        return render_template('recent_edits.html', page=page)
        
        
    def backlinks(self, page_name) :
        if len(page_name) > 64 :
            return Handler.render_page_simple('404 : page name too long'), 404 
        if not re.match('^[\w\d_]+$', page_name) :
            return Handler.render_page_simple('404 : page name contains unsupported characters'), 404 
       
        cur = self.con.cursor()

        cur.execute("SELECT * FROM page WHERE page_name=%s", (page_name,) )

        res = cur.fetchall()

        if not res :
            return Handler.render_page_simple('404 : nothing found'), 404 

        cur.execute("SELECT * FROM inter_page_links WHERE page_name_dst=%s LIMIT 5000", (page_name,) )

        res = cur.fetchall()

        html_lines = []
        for row in res :
            link_src = row[1]
            line = u"<a href='/{}/'>{}</a>".format(link_src, link_src)

            html_lines.append(line)

        backlink_lines = '<br>'.join(html_lines)

        page = {
            'page_name' : page_name,
            'backlink_lines' : backlink_lines
        }

        return render_template('backlinks.html', page=page)

    
    def search_page(self) :
        query = ''

        if 'q' in request.args :
            query = request.args['q']
            if len(query) == 0 :
            	query = ' '
                #return render_template('search_page.html', search_status='query is empty', search_results='')

        else :
            return render_template('search_page.html', search_status='', search_results='')

        if len(query) > 64 :
            return render_template('search_page.html', search_status='query is too long', search_results='')

        query = query.lower()
        
        query_to_db_list = ['%']
        for c in query :
            if c == ' ' :
                query_to_db_list.append('%')
            o = ord(c)
            if ( o >= 48 and o <=57 ) or ( o >= 97 and o <= 122 ) or o == 95 :
                query_to_db_list.append(c)
            else :
                pass

        query_to_db_list.append('%')

        query_to_db_str = ''.join(query_to_db_list)
        
        cur = self.con.cursor()
        cur.execute("SELECT * FROM page WHERE page_name LIKE %s", (query_to_db_str,) )
        res = cur.fetchall()

        html_lines = []
        for row in res :
            line = "<a href='/{}/'>{}</a>".format(row[0], row[0])
            html_lines.append(line)
        
        return render_template('search_page.html', query=request.args['q'], search_status='search results : ', search_results='<br>'.join(html_lines) )


    def random_page(self) :
        cur = self.con.cursor()
        cur.execute("SELECT * from page ORDER BY random() LIMIT 1")

        res = cur.fetchall()

        random_page = res[0][0]

        return redirect('/{}/'.format(random_page) )



    def create_page_render(self) :
        #this method doesn't want db so is it necessary to connect to db?
        page = {
            'create' : 1,
            'content' : ''
        }
        return render_template('edit_page.html', page=page)

    def edit_page_render(self, page_name) :
        version = 0
        if 'v' in request.args :
            if Handler.representsInt(request.args['v']) :
                version = int(request.args['v'])        

        if len(page_name) > 64 :
            return Handler.render_page_simple('bad request : page name too long'), 400
        if not re.match('^[\w\d_]+$', page_name) :
            return Handler.render_page_simple('bad request : page_name has other chars'), 400 

        cur = self.con.cursor()
        cur.execute("SELECT * FROM page WHERE page_name=%s", (page_name,) )
        res = cur.fetchall()

        if not res :
            return Handler.render_page_simple('Page you are trying to edit does not exist.'), 400

        page_row = res[0]
        version_count = page_row[1]
        version_latest = page_row[2]
        recent_view_datetime = page_row[3]

        if version <= 0 :
            version = version + version_latest


        cur.execute("SELECT * FROM pages_store WHERE page_name=%s AND version=%s", (page_name,version) )
        res = cur.fetchall()
        
        if not res :
            return Handler.render_page_simple('version does not exist'), 400

        pages_store_row = res[0]

        page_version = pages_store_row[1]
        diff = pages_store_row[2]
        creation_ts_datetime = pages_store_row[3]
        editor_name = pages_store_row[5]
        page_content = pages_store_row[6]

        line_count = pages_store_row[7]

        version_text = '{}{}'.format(page_version, ' (latest)' if page_version==version_latest else '')

        page = {
            'create' : 0,
            'page_name' : page_name,
            'version' : version,
            'version_text' : version_text,
            'content' : Handler.html_escape(page_content) 
        }

        return render_template('edit_page.html', page=page)


    def edit_page(self) :
        user_id = Handler.userId()
        version = 0
                
        page_name = Handler.single_linify(request.form['page_name']).strip().lower()
        content = request.form['content']
        editor_name = Handler.single_linify(request.form['editor_name']).strip()

        create = 0
        version_edited = 0
        force = 0

        if Handler.representsInt(request.form['create']) :
            create = int(request.form['create'])
        
        if create == 0 :
            if 'version_edited' in request.form and Handler.representsInt(request.form['version_edited']) :
                version_edited = int(request.form['version_edited'])

            if 'force' in request.form and request.form['force'].lower() == 'true' :
                force = 1

        # input processing and validation
        if len(page_name) > 64 :
            return 'page name too long', 400 
        if not re.match('^[\w\d_]+$', page_name) :
            return 'page name can only contain a-z 0-9 and _ characters', 400 

        restricted_page_names = ('create_page', 'recent_edits', 'search_page', 'edit_page', 'donate', 'deletion_logs', 'moderator_area', 'random_page')

        if page_name in restricted_page_names :
            return 'page name not allowed', 400

        if len(editor_name) > 30 :
            return 'name too long', 400
        if len(editor_name) == 0 :
            editor_name = 'Anonymous'

        if len(content) > 64000 :
            return 'content can only be 64000 characters long', 400
        
        line_count, inter_links = Handler.processContent(content)

        cur = self.con.cursor()
        cur.execute("SELECT * FROM edit_page(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (user_id, page_name, create, version_edited, force, editor_name,content,
                 line_count, inter_links ) )

        res = cur.fetchall()
        row = res[0]

        if row[0] < 0 :
            return row[1], 400
        
        self.con.commit()

        version_created = row[0]
        
        redirect_url = u'/{}/'.format(page_name)
        if create == 0 :
            redirect_url = redirect_url + u'?v={}'.format(version_created)

        returnable = {'redirect_url': redirect_url}
        return jsonify(returnable)


    @staticmethod
    def userId():
        strr = app.config['IP_HASH_STR'].format(request.remote_addr)
        sha256 = hashlib.sha256()
        sha256.update(strr)
        return base64.b64encode(sha256.digest())[:10]

    @staticmethod
    def representsInt(s):
        try: 
            int(s)
            return True
        except ValueError:
            return False
  
    @staticmethod
    def getAgeFromDatetime(d) :
        delta = datetime.utcnow() - d

        s = int(delta.total_seconds())

        if(s < 0) :
            return '0 second'
        if(s < 60) :
            return str(s) + ' seconds'
        if(s < 60*60) :
            minutes = int(s/60)
            r = '{} minute'.format(minutes)
            if minutes>1 :
                r = r + 's'
            return r
        if(s < 24*60*60) :
            hours = int(s/(60*60))
            r = '{} hour'.format(hours)
            if hours>1 :
                r = r + 's'
            return r

        days = int(s/(24*60*60))
        r = '{} day'.format(days)
        if days>1 :
            r = r + 's'
        return r
    
    @staticmethod
    def html_escape(str) :
        html_escape_table = {
        "&": "&amp;",
        '"': "&#34;",
        "'": "&#39;",
        ">": "&gt;",
        "<": "&lt;"
        }
        return "".join(html_escape_table.get(c,c) for c in str) #escape html entities

    @staticmethod
    def single_linify(txt) :
	lines = txt.splitlines()
	return ' '.join(lines)

    @staticmethod
    def processContent(content) :
        #note : this pattern is same as that in view_page, but only has internal part
        reg_str = '(?:^|\s|\\b)(?:https?:\/\/(?:www\.)?)?' + '(?P<internal>{}\/(?P<heart>[\w]{})\/?)'.format(app.config['SITE_NAME_REGEX'], '{1,64}' )


        url_pattern = re.compile(reg_str, re.IGNORECASE|re.MULTILINE)

        inter_links = []

        for m in url_pattern.finditer(content) :
            
            gd = m.groupdict()

            heart = gd['heart'].lower()  # no html_escape required

            inter_links.append(heart)

        inter_links = list( set(inter_links) )

        line_count = len( content.splitlines() )

        return ( line_count, inter_links )

    
    @staticmethod
    def tripcode_name(name) :
        name = name.strip()        
        m = re.match('^(.*?)#(.{1,})$', name) 

        trip_str = ''

        if m :
            trip_str = m.group(2).strip()

        if len(trip_str) == 0 :
            return u'<strong>{}</strong>'.format( Handler.html_escape(name) )
        else :
            strr = app.config['TRIP_HASH_STR'].format(trip_str)
            sha256 = hashlib.sha256()
            sha256.update(strr)
            trip =  base64.b64encode(sha256.digest())[:8]
            name_part = Handler.html_escape(m.group(1))

            return u'<strong>{}<span class="trip">!{}</span></strong>'.format(name_part, trip)

    @staticmethod
    def render_page_simple(msg) :
        return u"<span style='font-family:monospace;'>{}</span>".format(msg)


    @staticmethod
    def renderContent(content) :
        internal_sub_regex_str = '(?P<internal>{}\/(?P<heart>[\w]{})\/?)'.format(app.config['SITE_NAME_REGEX'], '{1,64}' )

        #'(https?:\/\/)(www\.)?(?<domain>[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6})(?<path>\/[-a-zA-Z0-9@:%_\/+.~#?&=]*)?'

        reg_str = '(?:^|\s|\\b)(?:(?P<external>https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}(?:\/[-a-zA-Z0-9@:%_\/.+~#?&=]*)?)|' + internal_sub_regex_str + ')'

        url_pattern = re.compile(reg_str, re.IGNORECASE|re.MULTILINE)

        lst = []
        run_index = 0

        for m in url_pattern.finditer(content) :

            named_group_idex = -1
            
            gd = m.groupdict()
            if gd['external'] != None :
                core = content[m.start(1):m.end(1)]
                extra = ''

                if core[-1] == '.' :
                    extra = '.'
                    core = core[:-1]

                core = Handler.html_escape( core )
                mid = u"<a href='{}'>{}</a>{}".format(core, core, extra)
                named_group_idx = 1

            elif gd['internal'] != None :
                heart = gd['heart']  # no html_escape required
                mid = "<a href='/{}/'>{}</a>".format(heart, heart)
                named_group_idx = 2
            
            lhs = Handler.html_escape( content[run_index:m.start(0)] + content[m.start(0):m.start(named_group_idx)] )
            rhs = Handler.html_escape( content[m.end(named_group_idx):m.end(0)] )

            lst.append(lhs)
            lst.append(mid)
            lst.append(rhs)

            run_index = m.end(0)            

        #add the last parts (if any)
        lst.append( Handler.html_escape(content[run_index:]) )

        return ''.join(lst)

                
