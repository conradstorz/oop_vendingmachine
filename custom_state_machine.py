class CustomStateMachine:
    def __init__(self, model, states, transitions, send_event=False, initial=None):
        self.model = model
        self.send_event = send_event
        self.states = {state["name"]: state for state in states}
        self.transitions = transitions
        self.state = initial
        # Optionally, attach trigger methods to the model:
        for transition in transitions:
            trigger_name = transition["trigger"]
            if not hasattr(model, trigger_name):
                # Attach a simple method that calls our trigger function
                setattr(model, trigger_name, lambda tn=trigger_name: self.trigger(tn))

    def trigger(self, trigger_name):
        # Find all transitions with the matching trigger from the current state.
        valid_transitions = [
            t
            for t in self.transitions
            if t["trigger"] == trigger_name
            and (
                isinstance(t["source"], list)
                and self.state in t["source"]
                or self.state == t["source"]
            )
        ]
        for t in valid_transitions:
            # Check conditions if provided.
            if "conditions" in t:
                # Assume conditions is a method name on the model that returns True/False.
                condition = getattr(self.model, t["conditions"])
                if not condition():
                    continue  # Skip this transition if condition fails.

            # Call the on_exit callback of the current state, if defined.
            exit_callback_name = f"on_exit_{self.state}"
            if hasattr(self.model, exit_callback_name):
                getattr(self.model, exit_callback_name)(None)

            # Transition to the new state.
            self.state = t["dest"]

            # Call the on_enter callback of the new state, if defined.
            enter_callback_name = f"on_enter_{self.state}"
            if hasattr(self.model, enter_callback_name):
                getattr(self.model, enter_callback_name)(None)

            # Transition complete.
            return
        # If no valid transition was found, optionally log or handle it.
        raise Exception(
            f"No valid transition for trigger {trigger_name} from state {self.state}"
        )

    def get_triggers(self, current_state):
        # Return a list of triggers that are valid from the current state.
        triggers = []
        for t in self.transitions:
            source = t["source"]
            if (
                isinstance(source, list) and current_state in source
            ) or current_state == source:
                triggers.append(t["trigger"])
        return triggers
