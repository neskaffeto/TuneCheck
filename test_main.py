import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from db import Base, get_db
import db_models as models

SQLALCHEMY_DB = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DB,
    connect_args={"check_same_thread":False},
    poolclass = StaticPool #in-memory tests
)
TestingSessionLocal = sessionmaker(autocommit = False, autoflush=False, bind=engine)

@pytest.fixture(name="db_session")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db=TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(name="client")
def fixture_client(db_session):
    def override_getdb():
        yield db_session
    app.dependency_overrides[get_db]=override_getdb
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture
def user_token(client):
    #register user and return auth headers
    username = "nesi"
    password = "parola1"

    client.post("/register", json={"username": username, "password": password, "role":"User"})

    response = client.post("/token", data={"username": username, "password": password})
    token = response.json()["access_token"]
    return {"Authorization":f"Bearer {token}"}

@pytest.fixture
def admin_token(client):
    #register admin and return auth headers
    username = "neskafe"
    password = "azsumshefa1"

    client.post("/register", json={"username": username, "password": password, "role":"Admin"})

    response = client.post("/token", data={"username": username, "password": password})
    token = response.json()["access_token"]
    return {"Authorization":f"Bearer {token}"}
    
#helpers

def create_user_get_token(client,username,password,role="User"):
    #register user
    client.post("/register", json={"username": username, "password": password, "role":role})

    #login
    response=client.post("/token", data={"username":username, "password":password})
    return response.json()["access_token"]

def get_auth(token):
    return {"Authorization": f"Bearer {token}"}

#user and authentication tests
def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message":"TuneCheck Web App"}


def test_registre_user(client):
    response = client.post(
        "/register",
        json={"username": "nessa", "password": "neznammanqk", "role":"User"})
    assert response.status_code==200
    data = response.json()
    assert data["username"]=="nessa"
    assert "id" in data

def test_login_succ(client):
    client.post("/register", json={"username": "denis", 
                                   "password": "kaloqnegei1",
                                     "role": "User"})
    response = client.post("/token", data={"username": "denis", 
                                   "password": "kaloqnegei1"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_dup_fail(client):
    data_user = {"username": "copycat", "password": "12345678", "role":"User"}
    client.post("/register", json=data_user)
    response = client.post("/register", json=data_user)
    assert response.status_code == 400

def test_get_usersme(client, user_token):
    response = client.get("/users/me", headers = user_token)
    assert response.status_code == 200
    assert response.json()["username"] == "nesi"

def test_get_all_users(client):
    response = client.get("/users/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_update(client, user_token):
    curr = client.get("/users/me", headers = user_token).json()
    user_id = curr["id"]

    #passwd change
    response = client.put(
        f"/user/{user_id}", json={"username": "nesi", "password": "paparola1"},
        headers = user_token
    )
    assert response.status_code == 200

    #login with new pass:
    login_test = client.post("/token", data={"username": "nesi", "password": "paparola1"})
    assert login_test.status_code == 200

def test_delete_user(client):
    client.post("/register", json={"username": "bokluk", "password": "mahaise", "role":"User"})
    token_use = client.post("/token", data={"username": "bokluk", "password": "mahaise"})
    token = token_use.json()["access_token"]
    headers={"Authorization":f"bearer {token}"}

    cl= client.get("/users/me", headers=headers).json()
    response = client.delete(f"/user/{cl["id"]}", headers = headers)
    assert response.status_code == 200
    assert "deleted" in response.json()["message"]

#song tests

def test_create_song_succ(client, admin_token):
    response = client.post(
        "/songs", json={"title" : "Losha", "singer" : "Andrea",
                        "album": "Andrea Top", "genre" : "pop folk",
                        "length" : 185, "date_of_publication" : "2022-04-06"},
                        headers = admin_token
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Losha"

def test_create_song_fail(client, user_token):
    response = client.post(
        "/songs", json={"title" : "Choban rap", "singer" : "Shmekera",
                        "album": "Izmislen", "genre" : "Rap",
                        "length" : 123, "date_of_publication" : "2025-03-04"},
                        headers = user_token
    )
    assert response.status_code == 403

def test_get_all_songs(client):
    response = client.get("/songs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_song_by_id(client, admin_token):
    song = client.post(
        "/songs", json={"title" : "DIS", "singer" : "Landcore",
                        "album": "FMI", "genre" : "Rap",
                        "length" : 199, "date_of_publication" : "2020-01-08"},
                        headers = admin_token
    ).json()
    res = client.get(f"/songs/{song["id"]}")
    assert res.status_code == 200
    assert res.json()["title"] == "DIS"

def test_update_song(client, admin_token):
    song = client.post(
        "/songs", json={"title" : "Fuel", "singer" : "Metallica",
                        "album": "ReLoad", "genre" : "Rock",
                        "length" : 199, "date_of_publication" : "2020-01-08"},
                        headers = admin_token
    ).json()
    #update title
    response = client.put(
        f"/songs/{song["id"]}", json={"title" : "Gorivo", "singer" : "Metallica",
                        "album": "ReLoad", "genre" : "Rock",
                        "length" : 199, "date_of_publication" : "2020-01-08"},
                        headers = admin_token)
    
    assert response.status_code == 200
    assert response.json()["title"] == "Gorivo"

def test_delete_song(client, admin_token):
    song = client.post("/songs", json = {"title" : "shit", "singer" : "baba",
                        "album": "nothing", "genre" : "techno",
                        "length" : 1, "date_of_publication" : "2000-01-08"},
                        headers = admin_token).json()
    res = client.delete(f"/songs/{song["id"]}", headers= admin_token)
    assert res.status_code == 200

    check = client.get(f"/songs/{song["id"]}")
    assert check.status_code == 404

#playlists

def test_create_playlist(client, user_token):
    response = client.post(
        "/playlists",
        json={"name": "All Time Hits"},
        headers=user_token
    )
    assert response.status_code == 200
    assert response.json()["name"] == "All Time Hits"

def test_create_dup_playlist_fail(client, user_token):
    client.post("/playlists", json={"name": "Dup"}, headers=user_token)
    response = client.post("/playlists", json={"name": "Dup"}, headers=user_token)
    assert response.status_code == 400

def test_add_song_to_playlist(client, user_token, admin_token):
    # 1. Admin creates song
    song = client.post("/songs", json={"title": "Loyvre",
                                            "singer": "Lorde", "album": "Melodrama",
                                             "genre": "Pop", "length": 165, 
                                             "date_of_publication": "2021-10-11"}, 
                                             headers=admin_token)
    song_id = song.json()["id"]
    pl_res = client.post("/playlists", json={"name": "New Play"}, headers=user_token)
    pl_id = pl_res.json()["id"]

    response = client.post(
        f"/playlists/{pl_id}/add/{song_id}",
        headers=user_token
    )
    assert response.status_code == 200
    assert "added" in response.json()["message"]

def test_update_playlist(client, user_token):
    pl = client.post("/playlists", json={"name": "Old Pl"}, headers=user_token).json()
    
    res = client.put(
        f"/playlists/{pl['id']}",
        json={"name": "New Pl"},
        headers=user_token
    )
    assert res.status_code == 200
    assert res.json()["name"] == "New Pl"

def test_delete_playlist(client, user_token):
    pl = client.post("/playlists", json={"name": "Awful"}, headers=user_token).json()
    
    res = client.delete(f"/playlists/{pl['id']}", headers=user_token)
    assert res.status_code == 200
    
    check = client.get(f"/playlists/{pl['id']}", headers=user_token)
    assert check.status_code == 404

# review 

def test_create_review(client, user_token, admin_token):
    song = client.post("/songs", json={"title": "abab", "singer": "abba",
                                       "album": "baba", "genre": "Pop", 
                                       "length": 1, 
                                       "date_of_publication": "2026-01-01"},
                                     headers=admin_token).json()
    response = client.post(
        f"/songs/{song['id']}/reviews",
        json={"rating": 5, "comment": "Amazing!"},
        headers=user_token
    )
    assert response.status_code == 200
    assert response.json()["rating"] == 5

def test_review_invalid_rating(client, user_token, admin_token):
    song = client.post("/songs", json={"title": "abab", "singer": "abba",
                                       "album": "baba", "genre": "Pop", 
                                       "length": 1, 
                                       "date_of_publication": "2026-01-01"},
                                     headers=admin_token).json()
    response = client.post(
        f"/songs/{song['id']}/reviews",
        json={"rating": 6, "comment": "Too good to be true"},
        headers=user_token
    )
    assert response.status_code == 400

def test_review_duplicate_fail(client, user_token, admin_token):
    song = client.post("/songs", json={"title": "abab", "singer": "abba",
                                       "album": "baba", "genre": "Pop", 
                                       "length": 1, 
                                       "date_of_publication": "2026-01-01"},
                                     headers=admin_token).json()
    client.post(f"/songs/{song['id']}/reviews", json={"rating": 5, "comment": "Yaya!"}, headers=user_token)
    response = client.post(f"/songs/{song['id']}/reviews", json={"rating": 4, "comment": "Lolz"}, headers=user_token)
    assert response.status_code == 400

#recommendations
def test_recommendations_empty(client, user_token):
    # Нов потребител без ревюта
    response = client.get("/recommendations", headers=user_token)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_recommendations_logic(client, user_token, admin_token):
    rock1 = client.post("/songs", json={"title": "Chop Suey", "singer": "SOAD", "album": "Nz", "genre": "Rock", "length": 122, "date_of_publication": "2022-01-05"}, headers=admin_token).json()
    rock2 = client.post("/songs", json={"title": "Cigaro", "singer": "SOAD", "album": "Nz", "genre": "Rock", "length": 188, "date_of_publication": "2022-06-06"}, headers=admin_token).json()
    pop1 = client.post("/songs", json={"title": "Dance Monkeys", "singer": "Ne znam", "album": "Mrazq q", "genre": "Pop", "length": 67, "date_of_publication": "2024-01-07"}, headers=admin_token).json()

    client.post(f"/songs/{rock1['id']}/reviews", json={"rating": 5, "comment": "Hell yeah"}, headers=user_token)

    rec_res = client.get("/recommendations", headers=user_token)
    rec_songs = rec_res.json()
    
    rec_ids = [s["id"] for s in rec_songs]
    assert rock2["id"] in rec_ids
    assert rock1["id"] not in rec_ids