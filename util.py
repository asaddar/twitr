from functools import wraps
from flask import request, jsonify
import jwt
from models import *
from config import app, db

def auth_required(f):
	@wraps(f)
	def decorated(*args, **kwargs):
		token = None

		if 'x-access-token' in request.headers:
			token = request.headers['x-access-token']

		if not token:
			return jsonify({'message' : 'missing token'}), 401

		try:
			data = jwt.decode(token, app.config['SECRET_KEY'])
			current_user = User.query.filter_by(id=data['user_id']).first()
		except:
			return jsonify({'message' : 'invalid token'}), 401

		return f(current_user, *args, **kwargs)

	return decorated

def table_row_to_dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = getattr(row, column.name)

    return d

def serialize(tweets):
	serialized = []
	for tweet in tweets:
		data = {}
		data['username'] = tweet.username
		data['id'] = tweet.id
		data['body'] = tweet.body
		data['author_id'] = tweet.author
		data['created_at'] = tweet.created_at
		data['number_replies'] = tweet.number_replies
		data['number_retweets'] = tweet.number_retweets
		data['number_likes'] = tweet.number_likes
		data['parent_id'] = tweet.parent_id
		serialized.append(data)

	return serialized