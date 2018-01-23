from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///twitter.db'
app.config['SECRET_KEY'] = 'secret'
db = SQLAlchemy(app)