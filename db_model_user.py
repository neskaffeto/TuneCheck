from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import Optional, List
import hashlib

app = FastAPI(title="TuneCheck DB")

DATABASE_URL = "sqlite:///./tunecheck.db"

#database setup

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread":False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base=declarative_base()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl = "token")

#DB models
#row in a table
class User(Base):
    __tablename__ = "users"

    id=Column(Integer,primary_key=True,index=True)
    username=Column(String(100), nullable=False, unique=True)
    password_hash=Column(String(100))
    role=Column(String(100), default="User")

Base.metadata.create_all(bind = engine)

#Pydantic models
#models of what we send and what we receive
class UserBase(BaseModel):
    username:str

class UserCreate(UserBase):
    password:str
    role: str = "User"

#fastapi works on model responses

class UserResponse(UserBase):
    #safety net
    id:int
    role:str
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

#------ENDPOINTS----
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