from fastapi import FastAPI
from app.routers import auth
from app.routers import add_user_api
from app.routers import add_project_api
from app.routers import add_holiday_api
app = FastAPI()

app.include_router(auth.router)

@app.get("/")
def root():
    return {"message": "HRMS Backend Running "}

app.include_router(add_user_api.router)

app.include_router(add_project_api.router)

app.include_router(add_holiday_api.router)