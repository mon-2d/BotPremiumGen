from flask import flask
from threading import thread

app = flask("")

@app.route('/')
    def home():
        return "Server Runing!"

def run():
    app.run(host='0.0.0.0',port=8888)

def server_on
    t = thread(targer=run)
    t.start()