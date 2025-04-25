import os
from fastapi import FastAPI, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, List

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

app = FastAPI()
Base = declarative_base()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Models
class Athlete(Base):
    __tablename__ = "athletes"
    id = Column(Integer, primary_key=True, index=True)
    strava_id = Column(Integer, unique=True, nullable=False)
    firstname = Column(String)
    lastname = Column(String)
    profile = Column(String)
    refresh_token = Column(String)
    access_token = Column(String)
    token_expires_at = Column(Integer)
    last_activities_update = Column(DateTime, default=datetime(2000,1,1))

class Activity(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True, index=True)
    strava_id = Column(Integer, unique=True, nullable=False)
    athlete_id = Column(Integer)
    name = Column(String)
    type = Column(String)
    distance = Column(Float) # in meters
    moving_time = Column(Integer)
    elapsed_time = Column(Integer)
    start_date = Column(DateTime)
    start_date_local = Column(DateTime)

Base.metadata.create_all(bind=engine)

# Utils
def get_month_range(year: int, month: int):
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end = datetime(year, month + 1, 1) - timedelta(seconds=1)
    return start, end

def get_week_ranges(year: int, month: int):
    start, end = get_month_range(year, month)
    current = start
    weeks = []
    while current < end:
        week_end = current + timedelta(days=6 - current.weekday())
        if week_end > end:
            week_end = end
        weeks.append((current, week_end))
        current = week_end + timedelta(days=1)
    return weeks

def refresh_access_token(athlete, session):
    now = int(datetime.utcnow().timestamp())
    if athlete.token_expires_at <= now:
        r = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": athlete.refresh_token
        })
        data = r.json()
        athlete.access_token = data["access_token"]
        athlete.refresh_token = data["refresh_token"]
        athlete.token_expires_at = data["expires_at"]
        session.commit()
    return athlete.access_token

def import_activities(session, athlete: Athlete):
    # Só atualiza se passou 1 hora da última importação
    now = datetime.now(timezone.utc)
    if not athlete.last_activities_update or (now - athlete.last_activities_update) > timedelta(hours=1):
        token = refresh_access_token(athlete, session)
        page = 1
        per_page = 100
        imported_ids = {x[0] for x in session.query(Activity.strava_id).filter(Activity.athlete_id == athlete.strava_id)}
        count = 0
        while True:
            r = requests.get(
                f"https://www.strava.com/api/v3/athlete/activities",
                headers={"Authorization": f"Bearer {token}"},
                params={"page": page, "per_page": per_page}
            )
            acts = r.json()
            if not isinstance(acts, list) or not acts:
                break
            for act in acts:
                if act["id"] in imported_ids:
                    continue
                a = Activity(
                    strava_id=act["id"],
                    athlete_id=athlete.strava_id,
                    name=act.get("name"),
                    type=act.get("type"),
                    distance=act.get("distance", 0),
                    moving_time=act.get("moving_time", 0),
                    elapsed_time=act.get("elapsed_time", 0),
                    start_date=datetime.fromisoformat(act["start_date"].replace("Z", "+00:00")),
                    start_date_local=datetime.fromisoformat(act["start_date_local"].replace("Z", "+00:00")),
                )
                session.add(a)
                count += 1
            session.commit()
            if len(acts) < per_page:
                break
            page += 1
        athlete.last_activities_update = now
        session.commit()
        return count
    return 0

# Rotas
@app.get("/")
def read_root():
    return {"message": "API do Ranking Strava funcionando!"}

@app.get("/auth/strava")
def auth_strava():
    url = (
        f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
        f"&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force"
        f"&scope=activity:read_all,profile:read_all"
    )
    return RedirectResponse(url)

@app.get("/auth/callback")
def callback(request: Request):
    code = request.query_params.get("code")
    db = SessionLocal()
    if not code:
        db.close()
        return HTMLResponse("<h3>Erro: código não encontrado</h3>")
    token_response = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code"
    })
    data = token_response.json()
    if 'athlete' in data:
        athlete = data['athlete']
        # upsert athlete
        db_athlete = db.query(Athlete).filter_by(strava_id=athlete['id']).first()
        if not db_athlete:
            db_athlete = Athlete(
                strava_id=athlete['id'],
                firstname=athlete['firstname'],
                lastname=athlete['lastname'],
                profile=athlete['profile'],
                refresh_token=data['refresh_token'],
                access_token=data['access_token'],
                token_expires_at=data['expires_at'],
                last_activities_update=datetime(2000,1,1, tzinfo=timezone.utc)
            )
            db.add(db_athlete)
            db.commit()
        else:
            db_athlete.firstname = athlete['firstname']
            db_athlete.lastname = athlete['lastname']
            db_athlete.profile = athlete['profile']
            db_athlete.refresh_token = data['refresh_token']
            db_athlete.access_token = data['access_token']
            db_athlete.token_expires_at = data['expires_at']
            db.commit()
        # Importa as atividades (apenas se passou 1h)
        import_activities(db, db_athlete)
        db.close()
        # Redireciona para o frontend (pode exibir tela de carregando ranking)
        return RedirectResponse(f"{FRONTEND_URL}?auth=success")
    db.close()
    return HTMLResponse("<h3>Erro ao autorizar com a Strava</h3>")

@app.get("/ranking")
def get_ranking(
    year: Optional[int] = Query(None), 
    month: Optional[int] = Query(None), 
    week: Optional[int] = Query(None),
    type: Optional[str] = Query(None)
):
    db = SessionLocal()
    now = datetime.now()
    if not year:
        year = now.year
    if not month:
        month = now.month

    # Filtro de datas
    if week:
        week_ranges = get_week_ranges(year, month)
        if week-1 < len(week_ranges):
            start, end = week_ranges[week-1]
        else:
            start, end = get_month_range(year, month)
    else:
        start, end = get_month_range(year, month)

    q = db.query(
        Athlete.firstname, Athlete.lastname, Athlete.profile,
        Activity.athlete_id,
        func.sum(Activity.distance).label("total_km")
    ).join(Athlete, Athlete.strava_id == Activity.athlete_id
    ).filter(
        Activity.start_date_local >= start,
        Activity.start_date_local <= end
    )

    if type and type != "all":
        q = q.filter(Activity.type == type.capitalize())

    q = q.group_by(Activity.athlete_id, Athlete.firstname, Athlete.lastname, Athlete.profile
    ).order_by(func.sum(Activity.distance).desc())

    results = q.all()
    db.close()
    return [
        {
            "atleta": f"{firstname} {lastname}",
            "profile": profile,
            "total_km": round((total_km or 0) / 1000, 2)
        }
        for firstname, lastname, profile, athlete_id, total_km in results
    ]

@app.get("/weeks")
def get_weeks(year: Optional[int] = None, month: Optional[int] = None):
    if not year or not month:
        now = datetime.now()
        year, month = now.year, now.month
    week_ranges = get_week_ranges(year, month)
    weeks = [
        {
            "week": idx + 1,
            "start": start.strftime("%d/%m"),
            "end": end.strftime("%d/%m")
        }
        for idx, (start, end) in enumerate(week_ranges)
    ]
    return weeks

@app.get("/last_update")
def last_update():
    db = SessionLocal()
    last = db.query(func.max(Athlete.last_activities_update)).scalar()
    db.close()
    if last:
        return {"last_update": last.isoformat()}
    return {"last_update": None}