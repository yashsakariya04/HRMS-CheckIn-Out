from fastapi import FastAPI
from backend.app.routers import auth
from backend.app.routers import add_user_api
from backend.app.routers import add_project_api
from backend.app.routers import add_holiday_api
from backend.app.routers import requests
from backend.app.routers import reporting
app = FastAPI()

@app.get("/")
def root():
    return {"message": "HRMS Backend Running "}

app.include_router(auth.router)

app.include_router(add_user_api.router)

app.include_router(add_project_api.router)

app.include_router(add_holiday_api.router)

app.include_router(requests.router)

app.include_router(reporting.router)

