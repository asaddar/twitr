from datetime import datetime
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from models import *
from config import app, db
from util import auth_required, table_row_to_dict, serialize

@app.route('/tweet/create', methods=['POST'])
@auth_required
def create_tweet(current_user):
	request_body = request.get_json()

	if len(request_body['tweet']) > 280 or len(request_body['tweet']) < 1:
		return jsonify({'error' : 'length of tweet must be 280 characters or less'}), 400

	hashtags = []
	substrings = request_body['tweet'].split()
	for substring in substrings:
		if substring.startswith('#'):
			existing_tag = Tag.query.filter_by(content=substring).first()
			if existing_tag:
				hashtags.append(existing_tag)
			else:
				tag = Tag(content=substring)
				db.session.add(tag)
				hashtags.append(tag)
	
	if request.args.get('in_reply_to_tweet_id'):
		if not substrings[0].startswith('@'):
			return jsonify({'error' : 'not valid reply'}), 400
		
		tweet = Tweet(body=request_body['tweet'], author=current_user.id, created_at=datetime.utcnow(), 
			number_replies=0, number_retweets=0, number_likes=0, 
			parent_id=request.args.get('in_reply_to_tweet_id'))

		in_reply_to_tweet = Tweet.query.filter_by(id=request.args.get('in_reply_to_tweet_id')).first()
		in_reply_to_tweet.number_replies += 1
	else:
		tweet = Tweet(body=request_body['tweet'], author=current_user.id, created_at=datetime.utcnow(), 
			number_replies=0, number_retweets=0, number_likes=0)

	db.session.add(tweet)
	db.session.flush()

	tagtweets = []
	for hashtag in hashtags:
		tagtweets.append(TagTweet(tweet_id=tweet.id, tag_id=hashtag.id))
	
	db.session.add_all(tagtweets)
	db.session.commit()
	
	return jsonify({'tweet' : table_row_to_dict(tweet)}), 200

@app.route('/tweet/<tweet_id>', methods=['GET'])
def get_tweet(tweet_id):
	tweet = Tweet.query.filter_by(id=tweet_id).first()

	if not tweet:
		return jsonify({'error' : 'tweet does not exist'}), 400

	author = User.query.filter_by(id=tweet.author).first()
	
	response = {}
	response['author'] = author.username
	response['id'] = tweet.id
	response['body'] = tweet.body
	response['created_at'] = tweet.created_at
	response['number_replies'] = tweet.number_replies
	response['number_retweets'] = tweet.number_retweets
	response['number_likes'] = tweet.number_likes
	response['parent_id'] = tweet.parent_id

	if tweet.parent_id != None:
		parent_tweet = Tweet.query.filter_by(id=tweet.parent_id).first()
		parent_tweet_author = User.query.filter_by(id=parent_tweet.author).first()

		response['in_reply_to'] = {}
		response['in_reply_to']['author'] = parent_tweet_author.username
		response['in_reply_to']['id'] = parent_tweet.id
		response['in_reply_to']['body'] = parent_tweet.body
		response['in_reply_to']['created_at'] = parent_tweet.created_at
		response['in_reply_to']['number_replies'] = parent_tweet.number_replies
		response['in_reply_to']['number_retweets'] = parent_tweet.number_retweets
		response['in_reply_to']['number_likes'] = parent_tweet.number_likes
		response['in_reply_to']['parent_id'] = parent_tweet.parent_id

	replies = db.engine.execute('''select user.username, tweet.*
		from user join tweet
		on user.id = tweet.author
		where tweet.parent_id = {}
		order by tweet.created_at asc'''.format(tweet_id))

	response['replies'] = []
	for reply in replies:
		tweet_data = {}
		tweet_data['id'] = reply.id
		tweet_data['body'] = reply.body
		tweet_data['author'] = reply.username
		tweet_data['created_at'] = reply.created_at
		tweet_data['number_replies'] = reply.number_replies
		tweet_data['number_retweets'] = reply.number_retweets
		tweet_data['number_likes'] = reply.number_likes
		tweet_data['parent_id'] = reply.parent_id
		response['replies'].append(tweet_data)

	return jsonify({'tweet' : response}), 200

@app.route('/home_timeline', methods=['GET'])
@auth_required
def home_timeline(current_user):
	max_date = request.args.get('max_date') or datetime.utcnow()
	timeline = db.engine.execute('''select * from (
			select user.username, tweet.*
			from user join tweet join follower
			on user.id = tweet.author and tweet.author = follower.followed_id
			where follower.follower_id = {user_id} and tweet.created_at <= "{max_date}"
			union
			select user.username, tweet.id, tweet.body, tweet.author, retweet.created_at, 
			tweet.number_replies, tweet.number_retweets, tweet.number_likes, tweet.parent_id
			from user join tweet left outer join retweet join follower
			on user.id = tweet.author and tweet.id = retweet.tweet_id and 
			retweet.user_id = follower.followed_id
			where follower.follower_id = {user_id} and retweet.created_at <= "{max_date}"
		)
		order by created_at desc
		limit 25'''.format(user_id=current_user.id, max_date=max_date))

	tweets = serialize(timeline)
	return jsonify({'home_timeline': tweets}), 200

@app.route('/<username>', methods=['GET'])
def user_tweets(username):
	user = User.query.filter_by(username=username).first()
	max_date = request.args.get('max_date') or datetime.utcnow()

	if not user:
		return jsonify({'error' : 'user does not exist'}), 400

	response = {}
	response['username'] = username
	response['following_count'] = Follower.query.filter_by(follower_id=user.id).count()
	response['follower_count'] = Follower.query.filter_by(followed_id=user.id).count()
	response['like_count'] = Like.query.filter_by(user_id=user.id).count()

	user_tweets = db.engine.execute('''select * from (
			select user.username, tweet.*
			from user join tweet
			on user.id = tweet.author
			where tweet.author = {user_id} and tweet.created_at <= "{max_date}"
			union
			select user.username, tweet.id, tweet.body, tweet.author, retweet.created_at, 
			tweet.number_replies, tweet.number_retweets, tweet.number_likes, tweet.parent_id
			from user join tweet left outer join retweet
			on user.id = tweet.author and tweet.id = retweet.tweet_id
			where retweet.user_id = {user_id} and retweet.created_at <= "{max_date}"
		)
		order by created_at desc
		limit 25'''.format(user_id=user.id, max_date=max_date))

	tweets = serialize(user_tweets)
	response['tweets'] = tweets
	response['tweet_count'] = len(tweets)

	return jsonify({'user': response}), 200

@app.route('/trending', methods=['GET'])
def trending():
	trends = db.engine.execute('''select tag.content, count(tag_tweet.id) as tag_count
		from tag join tag_tweet on tag.id = tag_tweet.tag_id
		group by tag.content
		order by tag_count desc
		limit 10''')

	return jsonify({'trending': [trend.content for trend in trends]}), 200

@app.route('/<username>/likes', methods=['GET'])
def user_likes(username):
	user = User.query.filter_by(username=username).first()
	max_date = request.args.get('max_date') or datetime.utcnow()
	likes = db.engine.execute('''select user.username, tweet.*
		from like join tweet join user
		on tweet.id = like.tweet_id and user.id = tweet.author
		where like.user_id = {} and like.created_at <= "{max_date}"
		order by like.created_at desc
		limit 25'''.format(user.id, max_date=max_date))

	response = serialize(likes)
	return jsonify({'likes' : response}), 200

@app.route('/hashtag/<tag>', methods=['GET'])
def hashtag_tweets(tag):
	hashtag = Tag.query.filter_by(content='#{}'.format(tag)).first()
	max_date = request.args.get('max_date') or datetime.utcnow()
	tagged_tweets = db.engine.execute('''select user.username, tweet.*
		from user join tweet join tag_tweet
		on user.id = tweet.author and tweet.id = tag_tweet.tweet_id
		where tag_tweet.tag_id = {} and tweet.created_at <= "{max_date}"
		order by tweet.created_at desc
		limit 25'''.format(hashtag.id, max_date=max_date))

	tweets = serialize(tagged_tweets)
	return jsonify({'tweets' : tweets}), 200

@app.route('/tweet/<tweet_id>', methods=['DELETE'])
@auth_required
def delete_tweet(current_user, tweet_id):
	tweet = Tweet.query.filter_by(id=tweet_id).first()
	if not tweet:
		return jsonify({'error' : 'tweet does not exist'}), 400

	if tweet.author != current_user.id:
		return jsonify({'error' : 'can not perform operation'}), 400

	db.engine.execute('delete from retweet where tweet_id = {}'.format(tweet_id))
	db.engine.execute('delete from like where tweet_id = {}'.format(tweet_id))
	db.engine.execute('delete from tag_tweet where tweet_id = {}'.format(tweet_id))
	db.engine.execute('update tweet set parent_id = null where parent_id = {}'.format(tweet_id))

	db.session.delete(tweet)
	db.session.commit()

	return jsonify({'message' : 'deleted tweet'}), 200

@app.route('/<username>/following', methods=['GET'])
def get_user_following(username):
	user = User.query.filter_by(username=username).first()
	following = db.session.execute('''select *
		from user join follower on user.id = follower.followed_id
		where follower_id = {user_id}
		order by follower.id desc'''.format(user_id=user.id))

	following_usernames = [followed.username for followed in following]
	return jsonify({'following' : following_usernames}), 200

@app.route('/<username>/followers', methods=['GET'])
def get_user_followers(username):
	user = User.query.filter_by(username=username).first()
	followers = db.session.execute('''select *
		from user join follower on user.id = follower.follower_id
		where followed_id = {user_id}
		order by follower.id desc'''.format(user_id=user.id))
	follower_usernames = [follower.username for follower in followers]
	return jsonify({'followers' : follower_usernames}), 200

@app.route('/tweet/retweet/<tweet_id>', methods=['POST'])
@auth_required
def retweet(current_user, tweet_id):
	existing_retweet = Retweet.query.filter_by(user_id=current_user.id, tweet_id=tweet_id).first()
	if existing_retweet:
		return jsonify({'error' : 'already retweeted'}), 400
	
	tweet = Tweet.query.filter_by(id=tweet_id).first()
	tweet.number_retweets += 1

	retweet = Retweet(tweet_id=tweet_id, user_id=current_user.id, created_at=datetime.utcnow())
	db.session.add(retweet)
	db.session.commit()

	return jsonify({'message' : 'retweeted'}), 200

@app.route('/tweet/unretweet/<tweet_id>', methods=['POST'])
@auth_required
def unretweet(current_user, tweet_id):
	retweet = Retweet.query.filter_by(user_id=current_user.id, tweet_id=tweet_id).first()
	if not retweet:
		return jsonify({'error' : 'have not retweeted this'}), 400
	
	tweet = Tweet.query.filter_by(id=tweet_id).first()
	tweet.number_retweets -= 1

	db.session.delete(retweet)
	db.session.commit()

	return jsonify({'message' : 'unretweeted'}), 200

@app.route('/tweet/like/<tweet_id>', methods=['POST'])
@auth_required
def like(current_user, tweet_id):
	existing_like = Like.query.filter_by(user_id=current_user.id, tweet_id=tweet_id).first()
	if existing_like:
		return jsonify({'error' : 'already liked'}), 400
	
	tweet = Tweet.query.filter_by(id=tweet_id).first()
	tweet.number_likes += 1

	like = Like(tweet_id=tweet_id, user_id=current_user.id, created_at=datetime.utcnow())
	db.session.add(like)
	db.session.commit()

	return jsonify({'message' : 'liked'}), 200

@app.route('/tweet/unlike/<tweet_id>', methods=['POST'])
@auth_required
def unlike(current_user, tweet_id):
	like = Like.query.filter_by(user_id=current_user.id, tweet_id=tweet_id).first()
	if not like:
		return jsonify({'error' : 'have not liked this'}), 400
	
	tweet = Tweet.query.filter_by(id=tweet_id).first()
	tweet.number_likes -= 1

	db.session.delete(like)
	db.session.commit()

	return jsonify({'message' : 'unliked'}), 200

@app.route('/follow/<user_id>', methods=['POST'])
@auth_required
def follow(current_user, user_id):
	existing_following = Follower.query.filter_by(follower_id=current_user.id, followed_id=user_id).first()
	if existing_following:
		return jsonify({'error' : 'already following user'}), 400

	following = Follower(follower_id=current_user.id, followed_id=user_id)
	db.session.add(following)
	db.session.commit()

	return jsonify({'message' : 'followed user'}), 200

@app.route('/unfollow/<user_id>', methods=['POST'])
@auth_required
def unfollow(current_user, user_id):
	following = Follower.query.filter_by(follower_id=current_user.id, followed_id=user_id).first()
	if not following:
		return jsonify({'error' : 'not following user'}), 400

	db.session.delete(following)
	db.session.commit()

	return jsonify({'message' : 'unfollowed user'}), 200

@app.route('/register', methods=['POST'])
def register():
	request_body = request.get_json()

	if not request_body['username'] or not request_body['password']:
		return jsonify({'error' : 'missing username and/or password'}), 400
	
	existing_user = User.query.filter_by(username=request_body['username']).first()
	if existing_user:
		return jsonify({'error' : 'username not available'}), 400

	hashed_password = generate_password_hash(request_body['password'], method='sha256')

	new_user = User(username=request_body['username'], hashed_password=hashed_password)
	
	db.session.add(new_user)
	db.session.commit()

	token = jwt.encode({'user_id' : new_user.id}, app.config['SECRET_KEY'])
	
	return jsonify({'token' : token.decode('UTF-8')}), 200

@app.route('/login', methods=['POST'])
def login():
	request_body = request.get_json()

	if not request_body['username'] or not request_body['password']:
		return jsonify({'error' : 'missing username and/or password'}), 400

	user = User.query.filter_by(username=request_body['username']).first()

	if not user:
		return jsonify({'error' : 'user does not exist'}), 400

	if check_password_hash(user.hashed_password, request_body['password']):
		token = jwt.encode({'user_id' : user.id}, app.config['SECRET_KEY'])

		return jsonify({'token' : token.decode('UTF-8')}), 200

	return jsonify({'error' : 'login failed'}), 400

if __name__ == '__main__':
	app.run()