from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import Athlete
from utils import refresh_access_token, get_activities
from datetime import datetime
import os, requests
from dotenv import load_dotenv
load_dotenv()

Base.metadata.create_all(bind=engine)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

@app.get("/")
def root():
    return {"message": "API do Ranking Strava com PostgreSQL está rodando!"}

@app.get("/auth/strava")
def auth_strava():
    url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=activity:read_all"
    return RedirectResponse(url)

@app.get("/auth/callback")
def callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    if not code:
        return HTMLResponse("<h3>Erro: código não encontrado</h3>")

    token_response = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code"
    }).json()

    if "athlete" in token_response:
        athlete = token_response["athlete"]
        strava_id = athlete["id"]
        existing = db.query(Athlete).filter_by(strava_id=strava_id).first()
        if not existing:
            novo = Athlete(
                strava_id=strava_id,
                firstname=athlete["firstname"],
                lastname=athlete["lastname"],
                refresh_token=token_response["refresh_token"]
            )
            db.add(novo)
            db.commit()
        return HTMLResponse(f"<h2>Autorizado com sucesso!</h2><p>{athlete['firstname']} agora está participando do ranking.</p>")
    return HTMLResponse("<h3>Erro ao autorizar com a Strava</h3>")

@app.get("/ranking")
def ranking(db: Session = Depends(get_db)):
    atletas = db.query(Athlete).all()
    resultado = []
    for atleta in atletas:
        token_data = refresh_access_token(atleta.refresh_token)
        access_token = token_data.get("access_token")
        atividades = get_activities(access_token)
        total_km = 0
        for atividade in atividades:
            if atividade["type"] in ["Run", "Walk"]:
                start_date = datetime.strptime(atividade["start_date"], "%Y-%m-%dT%H:%M:%SZ")
                now = datetime.utcnow()
                if start_date.month == now.month and start_date.year == now.year:
                    total_km += atividade["distance"] / 1000
        resultado.append({
            "atleta": f"{atleta.firstname} {atleta.lastname}",
            "total_km": round(total_km, 2)
        })
    resultado.sort(key=lambda x: x["total_km"], reverse=True)
    return resultado
