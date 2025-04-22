from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import requests, os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

app = FastAPI()

# CORS para permitir requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Banco de dados temporário (em memória para exemplo)
users = {}

@app.get("/")
def read_root():
    return {"message": "API do Ranking Strava funcionando!"}

@app.get("/auth/strava")
def auth_strava():
    url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=activity:read_all"
    return RedirectResponse(url)

@app.get("/auth/callback")
def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
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
        users[athlete['id']] = {
            "name": f"{athlete['firstname']} {athlete['lastname']}",
            "refresh_token": data['refresh_token'],
            "access_token": data['access_token'],
        }
        return HTMLResponse(f"<h2>Autorizado com sucesso!</h2><p>{athlete['firstname']} agora está participando do ranking.</p>")
    return HTMLResponse("<h3>Erro ao autorizar com a Strava</h3>")

@app.get("/ranking")
def get_ranking():
    # Simula um ranking básico usando os dados coletados
    ranking = [
        {"atleta": user["name"], "total_km": 42.5 + idx * 7.3}
        for idx, user in enumerate(users.values())
    ]
    return ranking