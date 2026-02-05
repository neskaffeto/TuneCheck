from pydantic import BaseModel
from typing import List
import datetime

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



