from config import db

class User(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(50), unique=True, nullable=False)
	hashed_password = db.Column(db.String, nullable=False)

class Tweet(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(db.String(280), nullable=False)
	author = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
	created_at = db.Column(db.DateTime, nullable=False)
	number_replies = db.Column(db.Integer, nullable=False)
	number_retweets = db.Column(db.Integer, nullable=False)
	number_likes = db.Column(db.Integer, nullable=False)
	parent_id = db.Column(db.Integer, db.ForeignKey('tweet.id'), nullable=True)

class Retweet(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	tweet_id = db.Column(db.Integer, db.ForeignKey('tweet.id'), nullable=False)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
	created_at = db.Column(db.DateTime, nullable=False)

class Like(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	tweet_id = db.Column(db.Integer, db.ForeignKey('tweet.id'), nullable=False)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
	created_at = db.Column(db.DateTime, nullable=False)

class Follower(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
	followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Tag(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	content = db.Column(db.String, unique=True, nullable=False)

class TagTweet(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	tweet_id = db.Column(db.Integer, db.ForeignKey('tweet.id'), nullable=False)
	tag_id = db.Column(db.Integer, db.ForeignKey('tag.id'), nullable=False)