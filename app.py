#!/usr/bin/env python
# coding=utf-8

"""
Flask-based Web application that demonstrates Twitter API

Used oauthlib for OAuth 2.0 implementation - https://github.com/simplegeo/python-oauth2
"""

from flask import Flask, render_template, redirect, flash, request
from flask_bootstrap import Bootstrap

from json import loads

import logging, urllib3, urllib, urlparse
import oauth2, hmac

from base64 import b64encode

from flask.ext.wtf import Form
from wtforms import StringField
from wtforms.validators import DataRequired, Length

from hashlib import sha1
from random import random
from time import time

app = Flask(__name__)
app.secret_key = "Secret key"
Bootstrap(app)

APP_TOKEN = {}

AUTHORIZATION_CODE_ENDPOINT='EXAMPLE'
MANAGER = urllib3.PoolManager()

CONSUMER_KEY='YOUR CONSUMER KEY'
CONSUMER_SECRET='YOUR CONSUMER SECRET'
CONSUMER = oauth2.Consumer(CONSUMER_KEY, CONSUMER_SECRET)

REQUEST_TOKEN={}
ACCESS_TOKEN={}


class TweetForm(Form):
    tweet = StringField('tweet', validators=[DataRequired(),Length(max=140)])

def get_oauth_header(method,url,status):
    parameters = {
        "oauth_consumer_key": CONSUMER_KEY,
        "oauth_nonce":  sha1(str(random)).hexdigest(),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time())),
        "oauth_token": ACCESS_TOKEN['oauth_token'],
        "oauth_version": "1.0",
        "status": status
    }

    """ Build the string that forms the base of the signature """
    base_string = "%s&%s&%s" % (method,urllib.quote(url,""),urllib.quote('&'.join(sorted("%s=%s" % (key,value)
                                                                                         for key,value in parameters.iteritems())),""))

    """ Create signature using signing key composed of consumer secret and token secret obtained during 3-legged dance"""
    signature = hmac.new("%s&%s" % (urllib.quote(CONSUMER_SECRET,""),urllib.quote(ACCESS_TOKEN['oauth_token_secret'],"")),
                         base_string,sha1)

    """ Add result to parameters and output is format required for header """
    parameters['oauth_signature'] = signature.digest().encode("base64").rstrip('\n')
    return 'OAuth %s' % ', '.join(sorted('%s="%s"' % (urllib.quote(key,""),urllib.quote(value,""))
                for key,value in parameters.iteritems() if key != 'status'))

def get_request_token():
    global REQUEST_TOKEN
    resp, content = oauth2.Client(CONSUMER).request('https://api.twitter.com/oauth/request_token', "GET")

    if resp['status'] != '200':
        print content
        raise Exception("Invalid response %s." % resp['status'])

    REQUEST_TOKEN = dict(urlparse.parse_qsl(content))
    return "%s?oauth_token=%s" % ('https://api.twitter.com/oauth/authorize', REQUEST_TOKEN['oauth_token'])

def get_app_token():
    try:
        app_token = MANAGER.urlopen('POST',
                                    'https://api.twitter.com/oauth2/token',
                                    headers={
                                        'Authorization': "Basic %s" % b64encode("%s:%s" % (CONSUMER_KEY,CONSUMER_SECRET)),
                                        'Content-Type': 'application/x-www-form-urlencoded',
                                    },
                                    body="grant_type=client_credentials")
        return loads(app_token.data)
    except: raise

@app.route("/tweet/<screen_name>", methods=['GET', 'POST'])
def dm_user(screen_name):
    if 'oauth_token' not in ACCESS_TOKEN:
        return redirect(get_request_token())

    else:
        """ Authorized so render template ready for message sending """
        form = TweetForm()
        if form.validate_on_submit():
            payload = "status=%s" % urllib.quote(form.tweet.data)

            auth_header = get_oauth_header('POST','https://api.twitter.com/1.1/statuses/update.json',urllib.quote(form.tweet.data))
            logging.log(logging.DEBUG,auth_header)

            """ Now send the tweet.... """
            try: response = MANAGER.urlopen("POST", 'https://api.twitter.com/1.1/statuses/update.json',
                                            headers={"Authorization": auth_header, 'Content-Type': 'application/x-www-form-urlencoded'},
                                            body=payload)
            except: raise

            flash("Tweet sent mentioning @%s" % screen_name) if response.status == 200 else flash("Error sending tweet: %s" % response.data)
            return redirect("/")

        return render_template('tweet.html', title="Send Tweet", form=form, message="Hello world @%s" % screen_name)

@app.route("/")
def handle_root():
    try:
        user_timeline = MANAGER.urlopen('GET',
                                        'https://api.twitter.com/1.1/statuses/user_timeline.json?screen_name=ProgrammableWeb',
                                        headers={'Authorization': 'Bearer %s' % APP_TOKEN['access_token']})
        return render_template('timeline.html',tweets=loads(user_timeline.data))
    except: raise

@app.route("/callback")
def handle_callback():
    global ACCESS_TOKEN

    token = oauth2.Token(REQUEST_TOKEN['oauth_token'], REQUEST_TOKEN['oauth_token_secret'])
    token.set_verifier(request.args.get('oauth_verifier'))
    client = oauth2.Client(CONSUMER, token)

    resp, content = client.request('https://api.twitter.com/oauth/access_token', "POST")
    ACCESS_TOKEN = dict(urlparse.parse_qsl(content))

    """ User now logged in so just redirect to the DM page """
    return redirect("/")

if __name__ == "__main__":
    try:
        APP_TOKEN = get_app_token()
        APP_TOKEN['access_token']
    except: raise

    app.run(port=8002, debug=True)
