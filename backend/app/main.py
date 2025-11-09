from fastapi import FastAPI

app = FastAPI(
    title="Bank FastAPI",
    description="Fully functional banking API built with FastAPI",
)

@app.get("/")
def home():
    return {"message": "Welcome to the Bank FastAPI application!"}