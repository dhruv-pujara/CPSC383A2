from aegis_game.stub import *


def think() -> None:
    """Do not remove this function, it must always be defined."""
    log("Thinking")

    # On the first round, send a request for surrounding information
    # by moving to the center (not moving). This will help initiate pathfinding.
    if get_round_number() == 1:
        move(Direction.CENTER)
        send_message("hello world", [])  # Broadcast to all teammates
        return

    # On subsequent rounds, read and log all received messages.
    messages = read_messages()
    log(messages)

    # Fetch the cell at the agent's current location.
    # If you want to check a different location, use `on_map(loc)` first
    # to ensure it's within the world bounds. The agent's own location is always valid.
    cell = get_cell_info_at(get_location())

    # Get the top layer at the agent's current location.
    # If a survivor is present, save it and end the turn.
    top_layer = cell.top_layer
    if isinstance(top_layer, Survivor):
        save()
        return
    
    if isinstance(top_layer, Rubble):
        dig()
        return

    # Default action: Move the agent north if no other specific conditions are met.
    survivors = get_survs()

    if survivors:
        current = get_location()
        target = min(survivors, key=lambda surv: current.distance_to(surv))

        dx = target.x - current.x
        dy = target.y - current.y
        direction = Direction.CENTER  # Default to no movement

        if dx > 0 and dy > 0:
            direction = Direction.SOUTHEAST
        elif dx > 0 and dy < 0:
            direction = Direction.NORTHEAST
        elif dx < 0 and dy > 0:
            direction = Direction.SOUTHWEST
        elif dx < 0 and dy < 0:
            direction = Direction.NORTHWEST
        elif dx > 0:
            direction = Direction.EAST
        elif dx < 0:
            direction = Direction.WEST
        elif dy > 0:
            direction = Direction.SOUTH
        elif dy < 0:
            direction = Direction.NORTH

        directions_to_try  = [
            direction,
            direction.rotate_left(),
            direction.rotate_right(),
            direction.rotate_left().rotate_left(),
            direction.rotate_right().rotate_right(),
            direction.rotate_left().rotate_left().rotate_left(),
            direction.rotate_right().rotate_right().rotate_right(),
            direction.get_opposite(),
        ]

        for d in directions_to_try:
            next_loc = current.add(d)

            if not on_map(next_loc):
                continue

            next_cell = get_cell_info_at(next_loc)
            if not next_cell.is_killer_cell():
                move(d)
                return
    
    move(Direction.CENTER)  # Default action if no survivors are found or if the path is blocked    
