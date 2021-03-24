#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

clients = []
class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        self.queue = queue.Queue()

    def put_queue(self, v):
        self.queue.put_nowait(v)

    def get_queue(self):
        return self.queue.get()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()        

def set_listener( entity, data ):
    ''' do something with the update ! '''
    for client in clients:

        client.put_queue(json.dumps({entity: data}))
        #print("queue",myWorld.queue)

myWorld.add_set_listener( set_listener )
        
@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return flask.redirect("/static/index.html")


def read_ws(ws,client):
    '''A greenlet function that reads from the websocket and updates the world'''
    # XXX: TODO IMPLEMENT ME
    try:
        while True:
            message = ws.receive()
            print("message",message)
            if(message):
                packet_received = json.loads(message)
                print("packet_received",packet_received)
                key = list(packet_received.keys())[0]
                myWorld.set(key, list(packet_received.values())[0])
                #myWorld.update_listeners(key)
            else:
                break
    except Exception as e:
        print(e)
    #return None

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    # XXX: TODO IMPLEMENT ME
    client = World()
    clients.append(client)
    g = gevent.spawn( read_ws, ws, client )
    try:
        while True:
            # block here
            msg = client.get_queue()
            print("msg",msg)
            ws.send(msg)
    except Exception as e:
        print("WS Error %s" % e)
    finally:
        clients.remove(client)
        gevent.kill(g)



# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    data = flask_post_json()
    if request.method == 'POST':
        # set new entities
        myWorld.set(entity, data)

    elif request.method =='PUT':
        for item in data.items():
            myWorld.update(entity, item[0], item[1])

    response = app.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response

@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    if request.method == 'POST':
        data = flask_post_json()
        myWorld.clear()
        for item in data.items():
            myWorld.set(item)
        response = app.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json'
        )
        return response
    elif request.method == 'GET':
        response = app.response_class(
            response=json.dumps(myWorld),
            status=200,
            mimetype='application/json'
        )
        return response


@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    response = app.response_class(
        response=json.dumps(myWorld.get(entity)),
        status=200,
        mimetype='application/json'
    )
    return response


@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()
    response = app.response_class(
        response=json.dumps(myWorld.world()),
        status=200,
        mimetype='application/json'
    )
    return response



if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
