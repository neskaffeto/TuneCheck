from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, Date, Table, ForeignKey, func, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import Optional, List
import hashlib
from sqlalchemy.orm import relationship
import datetime
from collections import Counter


app = FastAPI(title="TuneCheck DB")

DATABASE_URL = "sqlite:///./tunecheck.db"

#database setup

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread":False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base=declarative_base()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl = "token")

playlist_songs = Table(
    'playlist_songs', Base.metadata,
    Column('playlist_id', Integer, ForeignKey('playlists.id')),
    Column('song_id', Integer, ForeignKey('songs.id'))
)

#DB models
#row in a table
#USER
class User(Base):
    __tablename__ = "users"

    id=Column(Integer,primary_key=True,index=True)
    username=Column(String(100), nullable=False, unique=True)
    password_hash=Column(String(100))
    role=Column(String(100), default="User")

    playlists=relationship("Playlist", back_populates="owner")

#SONG
class Song(Base):
    __tablename__ = "songs"

    id=Column(Integer,primary_key=True,index=True)
    title=Column(String(100), nullable=False)
    album=Column(String(100))
    genre=Column(String(100))
    singer=Column(String(100), nullable=False)
    length=Column(Integer) #in minutes
    date_of_publication = Column(Date)
    
    reviews = relationship("Review", back_populates = "song")
    playlists = relationship("Playlist", secondary=playlist_songs, back_populates="songs")

#PLAYLIST
class Playlist(Base):
    __tablename__ = "playlists"

    id=Column(Integer,primary_key=True,index=True)
    name=Column(String(100), nullable=False)
    user_id=Column(Integer, ForeignKey("users.id"))

    #connect to owner
    owner= relationship("User", back_populates="playlists")
    #connect to songs; going through the table
    songs = relationship("Song", secondary=playlist_songs, back_populates="playlists")
    
#REVIEW
class Review(Base):
    __tablename__ = "reviews"

    id=Column(Integer,primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    song_id = Column(Integer, ForeignKey("songs.id"))
    rating = Column(Integer, nullable=False)
    comment = Column(String(500))

    song = relationship("Song", back_populates="reviews")

Base.metadata.create_all(bind = engine)

#Pydantic models
#models of what we send and what we receive

#~~~~~User~~~~~~~
class UserBase(BaseModel):
    username:str

class UserCreate(UserBase):
    password:str
    role: str = "User"

class UserResponse(UserBase):
    #safety net
    id:int
    role:str
    class Config:
        from_attributes = True

#~~~~~Song~~~~~~~

class SongCreate(BaseModel):
    title:str
    album:str
    genre:str
    singer:str
    length:int
    date_of_publication: datetime.date

class SongResponse(BaseModel):
    #safety net
    id:int
    title:str
    singer:str
    album:str
    class Config:
        from_attributes = True

#~~~~~Playlist~~~~~~~

class PlaylistCreate(BaseModel):
    name:str

class PlaylistResponse(BaseModel):
    id:int
    name:str
    user_id:int
    songs:List[SongResponse] =[]
    class Config:
        from_attributes = True

#~~~~~~Review~~~~~
class ReviewCreate(BaseModel):
    rating:int
    comment:str

class ReviewResponse(BaseModel):
    id:int
    rating:int
    comment:str
    user_id:int
    song_id:int
    class Config:
        from_attributes = True
def get_db():
    db=SessionLocal()
    try: 
        yield db
    finally:
        db.close()

def hash_password(password:str):
    return hashlib.sha256(password.encode()).hexdigest()

def get_current_user(token:str = Depends(oauth2_scheme), db:Session=Depends(get_db)):
    user = db.query(User).filter(User.username == token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid credentials")
    return user

def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="Only Admin can do this!")
    return current_user

#------ENDPOINTS----

#User Endpoints~~~~~~~~~~~~
@app.get("/")
def root():
    return {"message":"TuneCheck Web App"}

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id:int, db:Session=Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/register", response_model=UserResponse)
def create_user(user: UserCreate, db:Session=Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="User with this username already exists")
    new_user = User(
        username = user.username,
        password_hash = hash_password(user.password),
        role = user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    #form_data takes username and pass from login 
    user =  db.query(User).filter(User.username == form_data.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User doesn't exist")
    if str(user.password_hash) != hash_password(form_data.password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return {"access_token": user.username, "token_type" : "bearer"}

#update user
@app.put("/user/{user_id}", response_model=UserResponse)
def update_user(user_id:int, user_update:UserCreate, db:Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.id != user_id and current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="Not authorized to update this user")
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User doesn't exist")
    if user_update.username:
        db_user.username = user_update.username #type: ignore
    if user_update.password:
        db_user.password_hash = hash_password(user_update.password) #type: ignore
    
    db.commit()
    db.refresh(db_user)
    return db_user


#delete user
@app.delete("/user/{user_id}")
def delete_user(user_id:int, db:Session = Depends(get_db), current_user : User = Depends(get_current_user)):
    if current_user.id != user_id and current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="Not authorized to update this user")
    
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User doesn't exist")
    db.delete(db_user)
    db.commit()
    return {"message":"User deleted"}

@app.get("/users/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
#get all users
@app.get("/users/", response_model=List[UserResponse])
def get_all_users(db:Session=Depends(get_db)):
    return db.query(User).all()

#Song Endpoints~~~~~~~~~~~


#get song from DB
@app.get("/songs/{song_id}") #check if song is in the DB
def get_song(song_id:int, db:Session=Depends(get_db)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song

@app.post("/songs", response_model=SongResponse) #add song to the DB
def add_song(song:SongCreate, db:Session=Depends(get_db), current_user: User=Depends(get_current_user)):
    if current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="You don't have rights to add new songs" )
    exist_song =  db.query(Song).filter(Song.title == song.title, Song.singer == song.singer, Song.album == song.album).first()
    if exist_song:
        raise HTTPException(status_code=400, detail="This song is already added")
    #create new song
    new_song = Song (
        title = song.title,
        album = song.album,
        genre= song.genre,
        singer= song.singer,
        length= song.length,
        date_of_publication = song.date_of_publication 
    )
    db.add(new_song)
    db.commit()
    db.refresh(new_song)
    return new_song

#update song
@app.put("/songs/{song_id}", response_model=SongResponse)
def update_song(song_id:int, song_update:SongCreate, db:Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="Not authorized to update this song")
    db_song = db.query(Song).filter(Song.id == song_id).first()
    if not db_song:
        raise HTTPException(status_code=404, detail="Song doesn't exist")
    
    db_song.title = song_update.title #type: ignore
    db_song.album = song_update.album #type: ignore
    db_song.genre = song_update.genre #type: ignore
    db_song.singer = song_update.singer #type: ignore
    db_song.length = song_update.length #type: ignore
    db_song.date_of_publication = song_update.date_of_publication #type: ignore

    db.commit()
    db.refresh(db_song)
    return db_song


#delete song
@app.delete("/songs/{song_id}")
def delete_song(song_id:int, db:Session = Depends(get_db), current_user : User = Depends(get_current_user)):
    if current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="Not authorized to delete this song")
    
    db_song = db.query(Song).filter(Song.id == song_id).first()
    if not db_song:
        raise HTTPException(status_code=404, detail="Song doesn't exist")
    db.delete(db_song)
    db.commit()
    return {"message":"Song deleted"}

#Playlist Endpoints~~~~~~~~

@app.get("/playlists/{playlist_id}",response_model = PlaylistResponse) #check if playlist is in the DB
def get_playlist(playlist_id:int, db:Session=Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return playlist

@app.get("/playlists/me",response_model = List[PlaylistResponse]) #get all playlists
def get_my_playlists(db:Session=Depends(get_db), current_user: User=Depends(get_current_user)):
    return current_user.playlists

@app.post("/playlists", response_model = PlaylistResponse) #creating playlist and add it to the DB
def create_playlist(playlist:PlaylistCreate, db:Session=Depends(get_db), current_user: User=Depends(get_current_user)):
    #checks if the user already has a playlist with the same name
    exist_pl =  db.query(Playlist).filter(Playlist.name == playlist.name, Playlist.user_id == current_user.id).first()
    if exist_pl:
        raise HTTPException(status_code=400, detail="PLaylist with this name already exists in your library")
    #create new playlist
    new_playlist =  Playlist(name=playlist.name, user_id=current_user.id)
    db.add(new_playlist)
    db.commit()
    db.refresh(new_playlist)
    return new_playlist

@app.post("/playlists/{playlist_id}/add/{song_id}") #add song to a playlist
def add_song_to_pl(playlist_id:int, song_id:int,db:Session=Depends(get_db),current_user: User=Depends(get_current_user)):
    playlist =  db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="PLaylist doesn't exist")
    
    if playlist.user_id != current_user.id: #type: ignore
        raise HTTPException(status_code=403, detail="Not your playlist to add song to")
    
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song you want to add doesn't exist")
    
    if song in playlist.songs:
        raise HTTPException(status_code=400, detail="Song is already in playlist")
    
    playlist.songs.append(song)
    db.commit()

    return {"message": f"Song '{song.title}' added to playlist '{playlist.name}'"}

#update playlist
@app.put("/playlists/{playlist_id}", response_model=PlaylistResponse)
def update_playlist(playlist_id:int, playlist_update:PlaylistCreate, db:Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    playlist =  db.query(Playlist).filter(Playlist.id == playlist_id).first()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="PLaylist doesn't exist")
    
    if playlist.user_id != current_user.id: #type: ignore
        raise HTTPException(status_code=403, detail="Not your playlist to add song to")
    
    exist_pl =  db.query(Playlist).filter(Playlist.name == playlist_update.name, Playlist.user_id == current_user.id).first()
    if exist_pl:
        raise HTTPException(status_code=400, detail="PLaylist with this name already exists")
    
    playlist.name = playlist_update.name #type: ignore
    db.commit()
    db.refresh(playlist)
    return playlist


#delete playlist
@app.delete("/playlists/{playlist_id}")
def delete_playlist(playlist_id:int, db:Session = Depends(get_db), current_user : User = Depends(get_current_user)):
    playlist =  db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="PLaylist doesn't exist")
    
    if playlist.user_id != current_user.id: #type: ignore
        raise HTTPException(status_code=403, detail="Not authorized to delete this playlist")
    
    db.delete(playlist)
    db.commit()
    return {"message":"Playlist deleted"}

#REVIEW endpoints~~~~
@app.post("/songs/{song_id}/reviews", response_model=ReviewResponse)
def create_review(song_id:int,review:ReviewCreate,db:Session = Depends(get_db), current_user : User = Depends(get_current_user)):
    exist_song =  db.query(Song).filter(Song.id == song_id).first()
    if not exist_song:
        raise HTTPException(status_code=404, detail="Song not found")
    #validations
    exist_review = db.query(Review).filter(Review.user_id == current_user.id, Review.song_id == exist_song.id).first()
    if exist_review:
        raise HTTPException(status_code=400, detail="YOu have already written a review for this song")
    if review.rating <1 or review.rating>5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    #create new review
    new_review = Review (
        user_id = current_user.id,
        song_id = exist_song.id,
        rating = review.rating,
        comment = review.comment
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)
    return new_review

#Recommendations

@app.get("/recommendations", response_model=List[SongResponse]) 
def get_recommendations (current_user:  User = Depends(get_current_user), db:Session=Depends(get_db)):
    get_top_rated = db.query(Review).filter(Review.user_id == current_user.id, Review.rating >=4).all()
    
    recommended_songs = []

    if get_top_rated:
        genres = [review.song.genre for review in get_top_rated]
        if genres:
            most_common_genre = Counter(genres).most_common(1)[0][0]
            get_all_reviews = db.query(Review).filter(Review.user_id == current_user.id).all()
            rated_songs = [rev.song_id for rev in get_all_reviews]

            recommended_songs = db.query(Song).filter(Song.genre == most_common_genre, 
                                                      Song.id.notin_(rated_songs)
                                                      ).limit(3).all()
    if not recommended_songs:
        top_hits = (db.query(Review.song_id)
                    .group_by(Review.song_id)
                    .order_by(desc(func.avg(Review.rating)))
                    .limit(3).all())
        if top_hits:
            top_ids = [id for (id,) in top_hits]

            recommended_songs=db.query(Song).filter(Song.id.in_(top_ids)).all()
        else:
            recommended_songs = db.query(Song).limit(3).all()

    return recommended_songs
