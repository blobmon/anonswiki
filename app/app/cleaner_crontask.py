#!/user/bin/env python
# coding: utf-8 -*-

from app import app
import psycopg2
import time

def run():
    log("cleaner_crontask started")

    con = psycopg2.connect("dbname='anonswiki_db' user='anonswiki_role'")
	
    cur = con.cursor()

    cur.execute("SELECT * FROM cleanjob()" );

    #commit
    con.commit()
   
    con.close()
    log("cleaner_crontask finished")
    return 0

    
def log(msg):
    print "{} {}".format(time.strftime("%d/%m/%Y(%a)%H:%M:%S") , msg)

