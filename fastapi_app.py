from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from VMC_main import Machine

app = FastAPI(
    title="Vending Machine API",
    description="API to access machine activity and test functions",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as needed.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate the machine from your VMC_main.
machine = Machine()

# Pydantic model for coin insertion.
class CoinInsert(BaseModel):
    amount: int

@app.get("/machine/status")
def get_status():
    return {
        "state": machine.state,
        "deposit": machine.deposit,
        "stats": machine.stats,
    }

@app.post("/machine/button_press")
def simulate_button_press():
    try:
        machine.on_button_press(None)
        return {"message": "Button press simulated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/machine/coin_insert")
def simulate_coin_insert(coin: CoinInsert):
    try:
        # Call the machine's coin insert function, which updates the deposit.
        machine.on_coin_insert(coin.amount)
        return {"message": f"Coin inserted: {coin.amount}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/machine/vend_item")
def simulate_vend_item():
    try:
        machine.trigger("vend_item_now")
        return {"message": "Vend item triggered."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/machine/trigger")
def trigger_event(trigger_name: str):
    try:
        machine.trigger(trigger_name)
        return {"message": f"Triggered '{trigger_name}'."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Provide a root endpoint that returns your index.html.
@app.get("/")
def read_index():
    return FileResponse("static/index.html")

# Mount the static files on a subpath (here "/static").
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
