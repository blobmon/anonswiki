from flask import Flask

app = Flask(__name__)

app.config.from_pyfile('appconfig.cfg')

from flask import request, render_template, redirect, url_for
from handler import Handler

import uwsgi
import cleaner_crontask

#the cleaner cron setup
def cleaner_cron(signum) :
    cleaner_crontask.run()

uwsgi.register_signal(108, "", cleaner_cron)
uwsgi.add_cron(108,0,-1,-1,-1,-1)

@app.route('/')
def home():
    handler = Handler()
    return handler.view_page(app.config['WIKI_PAGE_NAME'])

@app.route('/<page_name>/')
def view_page(page_name):
    handler = Handler()
    return handler.view_page( page_name.lower() )

@app.route('/create_page/', methods=['GET'])
def create_page() :
    handler = Handler()
    return handler.create_page_render()

@app.route('/edit_page/', methods=['POST'])
def edit_page() :
    handler = Handler()
    return handler.edit_page()

@app.route('/<page_name>/edit/', methods=['GET'] )
def edit_page_render(page_name) :
    handler = Handler()
    return handler.edit_page_render(page_name)

@app.route('/<page_name>/version_history/', methods=['GET'])
def version_history(page_name) :
    handler = Handler()
    return handler.version_history(page_name)

@app.route('/<page_name>/backlinks/', methods=['GET'])
def backlinks(page_name) :
    handler = Handler()
    return handler.backlinks(page_name)

@app.route('/recent_edits/', methods=['GET'])
def recent_edits() :
    handler = Handler()
    return handler.recent_edits()

@app.route('/search_page/', methods=['GET'])
def search_page() :
    handler = Handler()
    return handler.search_page()

##################################
@app.errorhandler(404)
def page_not_found(e):
    return '<span style="font-family:monospace;">404 not found</span>', 404

@app.errorhandler(400)
def bad_req(e):
    return 'bad request', 400

@app.errorhandler(500)
def internal_sv_err(e):
    return 'server error', 500


