from loguru import logger

class CustomStateMachine:
    def __init__(self, model, states, transitions, send_event=False, initial=None):
        self.model = model
        self.send_event = send_event
        self.states = {state["name"]: state for state in states}
        self.transitions = transitions
        self.state = initial
        logger.debug("Initialized CustomStateMachine with initial state '{}'", self.state)
        # Attach trigger methods to the model if not already present.
        for transition in transitions:
            trigger_name = transition["trigger"]
            if not hasattr(model, trigger_name):
                setattr(model, trigger_name, lambda tn=trigger_name: self.trigger(tn))

    def trigger(self, trigger_name):
        logger.debug("Attempting trigger '{}' from state '{}'", trigger_name, self.state)
        valid_transitions = [
            t for t in self.transitions
            if t["trigger"] == trigger_name and (
                (isinstance(t["source"], list) and self.state in t["source"]) or (self.state == t["source"])
            )
        ]
        logger.debug("Found {} valid transitions for trigger '{}'", len(valid_transitions), trigger_name)
        for t in valid_transitions:
            if "conditions" in t:
                condition = getattr(self.model, t["conditions"])
                condition_result = condition()
                logger.debug("Evaluating condition '{}': {}", t["conditions"], condition_result)
                if not condition_result:
                    logger.debug("Condition '{}' failed, skipping this transition", t["conditions"])
                    continue

            exit_callback_name = f"on_exit_{self.state}"
            if hasattr(self.model, exit_callback_name):
                logger.debug("Calling exit callback '{}'", exit_callback_name)
                getattr(self.model, exit_callback_name)(None)

            logger.info("Transitioning from '{}' to '{}' via trigger '{}'", self.state, t["dest"], trigger_name)
            self.state = t["dest"]

            enter_callback_name = f"on_enter_{self.state}"
            if hasattr(self.model, enter_callback_name):
                logger.debug("Calling enter callback '{}'", enter_callback_name)
                getattr(self.model, enter_callback_name)(None)

            logger.debug("Completed trigger '{}'; new state: '{}'", trigger_name, self.state)
            return

        logger.error("No valid transition for trigger '{}' from state '{}'", trigger_name, self.state)
        raise Exception(f"No valid transition for trigger {trigger_name} from state {self.state}")

    def get_triggers(self, current_state):
        triggers = []
        for t in self.transitions:
            source = t["source"]
            if (isinstance(source, list) and current_state in source) or current_state == source:
                triggers.append(t["trigger"])
        logger.debug("Available triggers from state '{}': {}", current_state, triggers)
        return triggers
