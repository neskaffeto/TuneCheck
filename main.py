from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List
import hashlib
from fastapi.middleware.cors import CORSMiddleware
from collections import Counter

from db import engine, get_db, Base
import db_models as models
import pydantic_models

app = FastAPI(title="TuneCheck DB")

origins = [
    "http://localhost",
    "http://127.0.0.1:5500",
    "*"
]

app.add_middleware(CORSMiddleware,
                   allow_origins=origins,
                   allow_credentials = True,
                   allow_methods=["*"],
                   allow_headers=["*"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl = "token")

models.Base.metadata.create_all(bind = engine)


def hash_password(password:str):
    return hashlib.sha256(password.encode()).hexdigest()

def get_current_user(token:str = Depends(oauth2_scheme), db:Session=Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid credentials")
    return user

def get_admin_user(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="Only Admin can do this!")
    return current_user
#------ENDPOINTS----

#User Endpoints~~~~~~~~~~~~
@app.get("/")
def root():
    return {"message":"TuneCheck Web App"}

@app.get("/users/{user_id}", response_model=pydantic_models.UserResponse)
def get_user(user_id:int, db:Session=Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/register", response_model=pydantic_models.UserResponse)
def create_user(user: pydantic_models.UserCreate, db:Session=Depends(get_db)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="User with this username already exists")
    new_user = models.User(
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
    user =  db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User doesn't exist")
    if str(user.password_hash) != hash_password(form_data.password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return {"access_token": user.username, "token_type" : "bearer"}

#update user
@app.put("/user/{user_id}", response_model=pydantic_models.UserResponse)
def update_user(user_id:int, user_update:pydantic_models.UserCreate, db:Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.id != user_id and current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="Not authorized to update this user")
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
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
def delete_user(user_id:int, db:Session = Depends(get_db), current_user : models.User = Depends(get_current_user)):
    if current_user.id != user_id and current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="Not authorized to update this user")
    
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User doesn't exist")
    db.delete(db_user)
    db.commit()
    return {"message":"User deleted"}

@app.get("/users/me", response_model=pydantic_models.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user
#get all users
@app.get("/users/", response_model=List[pydantic_models.UserResponse])
def get_all_users(db:Session=Depends(get_db)):
    return db.query(models.User).all()

#Song Endpoints~~~~~~~~~~~
#get song from DB
@app.get("/songs/{song_id}") #check if song is in the DB
def get_song(song_id:int, db:Session=Depends(get_db)):
    song = db.query(models.Song).filter(models.Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song

@app.post("/songs", response_model=pydantic_models.SongResponse) #add song to the DB
def add_song(song:pydantic_models.SongCreate, db:Session=Depends(get_db), current_user: models.User=Depends(get_current_user)):
    if current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="You don't have rights to add new songs" )
    exist_song =  db.query(models.Song).filter(models.Song.title == song.title, models.Song.singer == song.singer, models.Song.album == song.album).first()
    if exist_song:
        raise HTTPException(status_code=400, detail="This song is already added")
    #create new song
    new_song = models.Song (
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
@app.put("/songs/{song_id}", response_model=pydantic_models.SongResponse)
def update_song(song_id:int, song_update:pydantic_models.SongCreate, db:Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="Not authorized to update this song")
    db_song = db.query(models.Song).filter(models.Song.id == song_id).first()
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
def delete_song(song_id:int, db:Session = Depends(get_db), current_user : models.User = Depends(get_current_user)):
    if current_user.role != "Admin": #type: ignore
        raise HTTPException(status_code=403, detail="Not authorized to delete this song")
    
    db_song = db.query(models.Song).filter(models.Song.id == song_id).first()
    if not db_song:
        raise HTTPException(status_code=404, detail="Song doesn't exist")
    db.delete(db_song)
    db.commit()
    return {"message":"Song deleted"}

#Playlist Endpoints~~~~~~~~

@app.get("/playlists/{playlist_id}",response_model = pydantic_models.PlaylistResponse) #check if playlist is in the DB
def get_playlist(playlist_id:int, db:Session=Depends(get_db)):
    playlist = db.query(models.Playlist).filter(models.Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return playlist

@app.get("/playlists/me",response_model = List[pydantic_models.PlaylistResponse]) #get all playlists
def get_my_playlists(db:Session=Depends(get_db), current_user: models.User=Depends(get_current_user)):
    return current_user.playlists

@app.post("/playlists", response_model = pydantic_models.PlaylistResponse) #creating playlist and add it to the DB
def create_playlist(playlist:pydantic_models.PlaylistCreate, db:Session=Depends(get_db), current_user: models.User=Depends(get_current_user)):
    #checks if the user already has a playlist with the same name
    exist_pl =  db.query(models.Playlist).filter(models.Playlist.name == playlist.name, models.Playlist.user_id == current_user.id).first()
    if exist_pl:
        raise HTTPException(status_code=400, detail="PLaylist with this name already exists in your library")
    #create new playlist
    new_playlist =  models.Playlist(name=playlist.name, user_id=current_user.id)
    db.add(new_playlist)
    db.commit()
    db.refresh(new_playlist)
    return new_playlist

@app.post("/playlists/{playlist_id}/add/{song_id}") #add song to a playlist
def add_song_to_pl(playlist_id:int, song_id:int,db:Session=Depends(get_db),current_user: models.User=Depends(get_current_user)):
    playlist =  db.query(models.Playlist).filter(models.Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="PLaylist doesn't exist")
    
    if playlist.user_id != current_user.id: #type: ignore
        raise HTTPException(status_code=403, detail="Not your playlist to add song to")
    
    song = db.query(models.Song).filter(models.Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song you want to add doesn't exist")
    
    if song in playlist.songs:
        raise HTTPException(status_code=400, detail="Song is already in playlist")
    
    playlist.songs.append(song)
    db.commit()

    return {"message": f"Song '{song.title}' added to playlist '{playlist.name}'"}

#update playlist
@app.put("/playlists/{playlist_id}", response_model=pydantic_models.PlaylistResponse)
def update_playlist(playlist_id:int, playlist_update:pydantic_models.PlaylistCreate, db:Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    playlist =  db.query(models.Playlist).filter(models.Playlist.id == playlist_id).first()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="PLaylist doesn't exist")
    
    if playlist.user_id != current_user.id: #type: ignore
        raise HTTPException(status_code=403, detail="Not your playlist to add song to")
    
    exist_pl =  db.query(models.Playlist).filter(models.Playlist.name == playlist_update.name, models.Playlist.user_id == current_user.id).first()
    if exist_pl:
        raise HTTPException(status_code=400, detail="PLaylist with this name already exists")
    
    playlist.name = playlist_update.name #type: ignore
    db.commit()
    db.refresh(playlist)
    return playlist


#delete playlist
@app.delete("/playlists/{playlist_id}")
def delete_playlist(playlist_id:int, db:Session = Depends(get_db), current_user : models.User = Depends(get_current_user)):
    playlist =  db.query(models.Playlist).filter(models.Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="PLaylist doesn't exist")
    
    if playlist.user_id != current_user.id: #type: ignore
        raise HTTPException(status_code=403, detail="Not authorized to delete this playlist")
    
    db.delete(playlist)
    db.commit()
    return {"message":"Playlist deleted"}

#REVIEW endpoints~~~~
@app.post("/songs/{song_id}/reviews", response_model=pydantic_models.ReviewResponse)
def create_review(song_id:int,review:pydantic_models.ReviewCreate,db:Session = Depends(get_db), current_user : models.User = Depends(get_current_user)):
    exist_song =  db.query(models.Song).filter(models.Song.id == song_id).first()
    if not exist_song:
        raise HTTPException(status_code=404, detail="Song not found")
    #validations
    exist_review = db.query(models.Review).filter(models.Review.user_id == current_user.id, models.Review.song_id == exist_song.id).first()
    if exist_review:
        raise HTTPException(status_code=400, detail="YOu have already written a review for this song")
    if review.rating <1 or review.rating>5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    #create new review
    new_review = models.Review (
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

@app.get("/recommendations", response_model=List[pydantic_models.SongResponse]) 
def get_recommendations (current_user:  models.User = Depends(get_current_user), db:Session=Depends(get_db)):
    get_top_rated = db.query(models.Review).filter(models.Review.user_id == current_user.id, models.Review.rating >=4).all()
    
    recommended_songs = []

    if get_top_rated:
        genres = [review.song.genre for review in get_top_rated]
        if genres:
            most_common_genre = Counter(genres).most_common(1)[0][0]
            get_all_reviews = db.query(models.Review).filter(models.Review.user_id == current_user.id).all()
            rated_songs = [rev.song_id for rev in get_all_reviews]

            recommended_songs = db.query(models.Song).filter(models.Song.genre == most_common_genre, 
                                                      models.Song.id.notin_(rated_songs)
                                                      ).limit(3).all()
    if not recommended_songs:
        top_hits = (db.query(models.Review.song_id)
                    .group_by(models.Review.song_id)
                    .order_by(desc(func.avg(models.Review.rating)))
                    .limit(3).all())
        if top_hits:
            top_ids = [id for (id,) in top_hits]

            recommended_songs=db.query(models.Song).filter(models.Song.id.in_(top_ids)).all()
        else:
            recommended_songs = db.query(models.Song).limit(3).all()

    return recommended_songs
