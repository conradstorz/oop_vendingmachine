from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from VMC_main import Machine
from fastapi.staticfiles import StaticFiles
import uvicorn

# Create the FastAPI application
app = FastAPI(
    title="Vending Machine API",
    description="API to access machine activity and test functions",
    version="1.0"
)

# Mount the static directory with html=True to serve index.html at the root.
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Instantiate the machine once at startup.
# (The Machine class sets up the hardware abstractions, state machine, watchdog, etc.)
machine = Machine()

# Pydantic model for coin insertion
class CoinInsert(BaseModel):
    amount: int

@app.get("/machine/status")
def get_status():
    """
    Returns the current machine status, including state, deposit, and statistics.
    """
    return {
        "state": machine.state,
        "deposit": machine.deposit,
        "stats": machine.stats,
    }

@app.post("/machine/button_press")
def simulate_button_press():
    """
    Simulate a button press event.
    """
    try:
        machine.on_button_press(None)
        return {"message": "Button press simulated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/machine/coin_insert")
def simulate_coin_insert(coin: CoinInsert):
    """
    Simulate a coin insert event by providing the coin amount.
    """
    try:
        machine.on_coin_insert(coin.amount)
        return {"message": f"Coin inserted: {coin.amount}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/machine/vend_item")
def simulate_vend_item():
    """
    Simulate the vend item event.
    """
    try:
        machine.trigger("vend_item_now")
        return {"message": "Vend item triggered."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/machine/trigger")
def trigger_event(trigger_name: str):
    """
    Trigger an arbitrary event on the state machine.
    Useful for testing specific transitions.
    """
    try:
        machine.trigger(trigger_name)
        return {"message": f"Triggered '{trigger_name}'."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Run the FastAPI app using uvicorn.
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
