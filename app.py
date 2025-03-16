# app.py
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    book_votes = db.relationship('BookVote', backref='user', lazy=True)
    video_votes = db.relationship('VideoVote', backref='user', lazy=True)
    comment_votes = db.relationship('CommentVote', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='post', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    votes = db.relationship('CommentVote', backref='comment', lazy=True)
    
    @property
    def vote_count(self):
        return sum(vote.value for vote in self.votes)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    votes = db.relationship('BookVote', backref='book', lazy=True)
    
    @property
    def vote_count(self):
        return sum(vote.value for vote in self.votes)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    youtube_id = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    votes = db.relationship('VideoVote', backref='video', lazy=True)
    
    @property
    def vote_count(self):
        return sum(vote.value for vote in self.votes)

class BookVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    value = db.Column(db.Integer, default=1)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'book_id', name='unique_user_book_vote'),)

class VideoVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    value = db.Column(db.Integer, default=1)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'video_id', name='unique_user_video_vote'),)

class CommentVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    value = db.Column(db.Integer, default=1)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'comment_id', name='unique_user_comment_vote'),)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def home():
    # Fetch news from API
    news_api_key = os.getenv('NEWS_API_KEY', '')
    if news_api_key:
        try:
            url = f'https://newsapi.org/v2/top-headlines?category=business&apiKey={news_api_key}'
            response = requests.get(url)
            news = response.json().get('articles', [])
            # Filter only articles with images
            news = [article for article in news if article.get('urlToImage')]
        except Exception as e:
            news = []
            print(f"Error fetching news: {e}")
    else:
        news = []
    
    return render_template('home.html', news=news)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        else:
            flash('Login failed. Please check your username and password.', 'danger')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('signup'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('signup'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Account created successfully. You can now login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/forum')
def forum():
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('forum.html', posts=posts)

@app.route('/forum/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        
        if not title or not content:
            flash('Title and content are required.', 'danger')
            return redirect(url_for('new_post'))
        
        post = Post(title=title, content=content, author=current_user)
        db.session.add(post)
        db.session.commit()
        
        flash('Post created successfully.', 'success')
        return redirect(url_for('forum'))
    
    return render_template('new_post.html')

@app.route('/forum/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post_detail.html', post=post)

@app.route('/forum/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content')
    
    if not content:
        flash('Comment cannot be empty.', 'danger')
        return redirect(url_for('post_detail', post_id=post_id))
    
    comment = Comment(content=content, post=post, author=current_user)
    db.session.add(comment)
    db.session.commit()
    
    return redirect(url_for('post_detail', post_id=post_id))

# Fix for comment voting in app.py
@app.route('/vote/comment/<int:comment_id>/<int:value>')
@login_required
def vote_comment(comment_id, value):
    comment = Comment.query.get_or_404(comment_id)
    
    # Check if user already voted
    existing_vote = CommentVote.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()
    
    if existing_vote:
        if existing_vote.value == value:
            # Remove vote if same value
            db.session.delete(existing_vote)
        else:
            # Change vote value
            existing_vote.value = value
    else:
        # Create new vote
        vote = CommentVote(user_id=current_user.id, comment_id=comment_id, value=value)
        db.session.add(vote)
    
    db.session.commit()
    return redirect(url_for('post_detail', post_id=comment.post_id))

@app.route('/books')
def books():
    books = Book.query.order_by(Book.date_added.desc()).all()
    # Sort books by vote count
    sorted_books = sorted(books, key=lambda book: book.vote_count, reverse=True)
    return render_template('books.html', books=sorted_books)

@app.route('/books/new', methods=['GET', 'POST'])
@login_required
def new_book():
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        description = request.form.get('description')
        image_url = request.form.get('image_url')
        
        if not title or not author:
            flash('Title and author are required.', 'danger')
            return redirect(url_for('new_book'))
        
        book = Book(title=title, author=author, description=description, 
                    image_url=image_url, user_id=current_user.id)
        db.session.add(book)
        db.session.commit()
        
        flash('Book added successfully.', 'success')
        return redirect(url_for('books'))
    
    return render_template('new_book.html')

@app.route('/vote/book/<int:book_id>')
@login_required
def vote_book(book_id):
    book = Book.query.get_or_404(book_id)
    
    # Check if user already voted
    existing_vote = BookVote.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    
    if existing_vote:
        # Remove vote if already voted
        db.session.delete(existing_vote)
    else:
        # Create new vote
        vote = BookVote(user_id=current_user.id, book_id=book_id)
        db.session.add(vote)
    
    db.session.commit()
    return redirect(url_for('books'))

@app.route('/videos')
def videos():
    videos = Video.query.order_by(Video.date_added.desc()).all()
    # Sort videos by vote count
    sorted_videos = sorted(videos, key=lambda video: video.vote_count, reverse=True)
    return render_template('videos.html', videos=sorted_videos)

@app.route('/videos/new', methods=['GET', 'POST'])
@login_required
def new_video():
    if request.method == 'POST':
        title = request.form.get('title')
        youtube_id = request.form.get('youtube_id')
        description = request.form.get('description')
        
        if not title or not youtube_id:
            flash('Title and YouTube video ID are required.', 'danger')
            return redirect(url_for('new_video'))
        
        # Extract video ID if full URL is provided
        if 'youtube.com' in youtube_id or 'youtu.be' in youtube_id:
            if 'v=' in youtube_id:
                youtube_id = youtube_id.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in youtube_id:
                youtube_id = youtube_id.split('youtu.be/')[1].split('?')[0]
        
        video = Video(title=title, youtube_id=youtube_id, description=description, user_id=current_user.id)
        db.session.add(video)
        db.session.commit()
        
        flash('Video added successfully.', 'success')
        return redirect(url_for('videos'))
    
    return render_template('new_video.html')

@app.route('/vote/video/<int:video_id>')
@login_required
def vote_video(video_id):
    video = Video.query.get_or_404(video_id)
    
    # Check if user already voted
    existing_vote = VideoVote.query.filter_by(user_id=current_user.id, video_id=video_id).first()
    
    if existing_vote:
        # Remove vote if already voted
        db.session.delete(existing_vote)
    else:
        # Create new vote
        vote = VideoVote(user_id=current_user.id, video_id=video_id)
        db.session.add(vote)
    
    db.session.commit()
    return redirect(url_for('videos'))

@app.route('/ai_finance')
def ai_finance():
    return render_template('ai_finance.html')

@app.route('/ai_query', methods=['POST'])
def ai_query():
    query = request.form.get('query')
    if not query:
        return jsonify({'error': 'Query cannot be empty'}), 400
    
    try:
        # Using the pollinations.ai API
        finance_prompt = f"Answer this finance-related question: {query}"
        response = requests.post(
            'https://text.pollinations.ai/',
            json={'prompt': finance_prompt}
        )
        
        if response.status_code == 200:
            return jsonify({'response': response.text})
        else:
            # Fallback to GET if POST fails
            response = requests.get(f'https://text.pollinations.ai/{finance_prompt}')
            if response.status_code == 200:
                return jsonify({'response': response.text})
            else:
                return jsonify({'error': 'Failed to get AI response'}), 500
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/toggle_theme', methods=['POST'])
def toggle_theme():
    theme = request.form.get('theme', 'light')
    session['theme'] = theme
    return jsonify({'theme': theme})

@app.context_processor
def inject_theme():
    return {'theme': session.get('theme', 'light')}

# Create database tables
@app.before_first_request
def create_tables():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)