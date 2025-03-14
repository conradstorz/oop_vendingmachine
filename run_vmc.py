import tkinter as tk
from tkinter import ttk
import threading
import time
from VMC_main import Machine  # Your FSM is defined here

class FSM_GUI:
    def __init__(self, master):
        self.master = master
        self.master.title("FSM State Monitor")
        
        # Create the Machine instance (your FSM)
        self.machine = Machine()
        
        # Create labels to show the machine state and deposit
        self.state_label = ttk.Label(master, text="State: " + self.machine.state)
        self.state_label.pack(pady=10)
        
        self.deposit_label = ttk.Label(master, text="Deposit: " + str(self.machine.deposit))
        self.deposit_label.pack(pady=10)
        
        # Create buttons to simulate user input events
        self.button_press_btn = ttk.Button(master, text="Simulate Button Press", command=self.simulate_button_press)
        self.button_press_btn.pack(pady=5)
        
        self.insert_coin_btn = ttk.Button(master, text="Simulate Coin Insert", command=self.simulate_coin_insert)
        self.insert_coin_btn.pack(pady=5)
        
        self.vend_item_btn = ttk.Button(master, text="Simulate Vend Item", command=self.simulate_vend_item)
        self.vend_item_btn.pack(pady=5)
        
        # Start a background thread to update the display periodically.
        self.updater = threading.Thread(target=self.update_ui, daemon=True)
        self.updater.start()
    
    def simulate_button_press(self):
        # Call the machine's button press callback directly.
        self.machine.on_button_press(None)
    
    def simulate_coin_insert(self):
        # Simulate coin insert; here we assume a coin value of 1.
        self.machine.on_coin_insert(1)
    
    def simulate_vend_item(self):
        # Simulate a vend command (trigger the vend_item_now transition).
        self.machine.trigger("vend_item_now")
    
    def update_ui(self):
        while True:
            # Update the state and deposit labels with the current values.
            state_text = "State: " + self.machine.state
            deposit_text = "Deposit: " + str(self.machine.deposit)
            self.state_label.config(text=state_text)
            self.deposit_label.config(text=deposit_text)
            time.sleep(0.5)

def main():
    root = tk.Tk()
    app = FSM_GUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
