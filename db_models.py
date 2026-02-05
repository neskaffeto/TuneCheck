#DB models
#row in a table
#USER
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Table
from sqlalchemy.orm import relationship
from db import Base

playlist_songs = Table(
    'playlist_songs', Base.metadata,
    Column('playlist_id', Integer, ForeignKey('playlists.id')),
    Column('song_id', Integer, ForeignKey('songs.id'))
)

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



