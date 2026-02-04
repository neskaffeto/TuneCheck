from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, Date, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import Optional, List
import hashlib
from sqlalchemy.orm import relationship
import datetime


app = FastAPI(title="TuneCheck DB")

DATABASE_URL = "sqlite:///./tunecheck.db"

#database setup

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread":False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base=declarative_base()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl = "token")


#DB models
#row in a table
#USER
class User(Base):
    __tablename__ = "users"

    id=Column(Integer,primary_key=True,index=True)
    username=Column(String(100), nullable=False, unique=True)
    password_hash=Column(String(100))
    role=Column(String(100), default="User")

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
class UserBase(BaseModel):
    username:str

class UserCreate(UserBase):
    password:str
    role: str = "User"

class SongCreate(BaseModel):
    title:str
    album:str
    genre:str
    singer:str
    length:int
    date_of_publication: datetime.date

class UserResponse(UserBase):
    #safety net
    id:int
    role:str
    class Config:
        from_attributes = True

class SongResponse(BaseModel):
    #safety net
    id:int
    title:str
    singer:str
    album:str
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

#User Endpoints
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

#Song Endpoints
#get song from DB
@app.get("/songs/{song_id}") #check if song is in the DB
def get_song(song_id:int, db:Session=Depends(get_db)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song

@app.post("/songs") #add song to the DB
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

