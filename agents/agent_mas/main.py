from aegis_game.stub import *
import heapq

help_requests_sent = set()

DIR_ORDER = [
    Direction.NORTH,
    Direction.NORTHEAST,
    Direction.EAST,
    Direction.SOUTHEAST,
    Direction.SOUTH,
    Direction.SOUTHWEST,
    Direction.WEST,
    Direction.NORTHWEST,
]

def think() -> None:

    global last_location
    current = get_location()
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

    my_id = get_id()
    help_target = None
    best_help_distance = float('inf')
    current_location = get_location()
    fallback_dist = float('inf')
    fallback_target = None

    for msg in messages:
        parts = msg.message.split() 
        
        if len(parts) == 4 and parts[0] == "HELP":
            x = int(parts[1])
            y = int(parts[2])
            requester_id = int(parts[3])

            if requester_id == my_id:
                continue
            
            loc = Location(x,y)
            dist = current_location.distance_to(loc)
            
            if dist <= 25 and dist < best_help_distance:
                best_help_distance = dist
                help_target = loc
                log(f"Considering help request at {loc} from agent {requester_id} with distance {dist}")

            if dist < fallback_dist:
                fallback_dist = dist
                fallback_target = loc
    if help_target is None:
        help_target = fallback_target


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
        log(f"Rubble here needs {top_layer.agents_required} agents and {top_layer.energy_required} energy.")
        
        if top_layer.agents_required == 1:
            dig()
            return
        
        # needs more than 1 agent, ask for help
        loc = get_location()
        if (loc.x, loc.y) not in help_requests_sent:
            send_message(f"HELP {loc.x} {loc.y} {get_id()}", [])  # Broadcast a help request with the location of the rubble
            help_requests_sent.add((loc.x, loc.y))

        move(Direction.CENTER)  # Stay in place to wait for teammates to help with the rubble
        return

    survivors = get_survs()
    current = get_location()

    if help_target is not None:
        target = help_target
    elif survivors:
        target = min(survivors, key=lambda surv: current.distance_to(surv))  # Closest survivor
    else:
        move(Direction.CENTER)  # No survivors found, stay in place
        return

    path = a_star(current, target)

    if path is None or len(path) < 2:
        move(Direction.CENTER)  # No path found or already at target
        return

    next_loc = path[1]
    direction = next_direction(current, next_loc)
    move(direction)
    return



def get_neighbors(location: Location) -> list[Location]:
    neighbors = []

    for direction in DIR_ORDER:
        neighbor_location = location.add(direction)

        if not on_map(neighbor_location):
            continue

        cell_info = get_cell_info_at(neighbor_location)
        if cell_info.is_killer_cell():
            continue

        neighbors.append(neighbor_location)

    return neighbors

def heuristic(current: Location, goal: Location) -> int:
    dx = abs(current.x - goal.x)
    dy = abs(current.y - goal.y)
    return max(dx, dy)

def a_star(start: Location, goal: Location) -> list[Location] | None:
    if start == goal:
        return [start]

    # heap entries: (f, tie, g, node)
    open_heap: list[tuple[int, int, int, Location]] = []
    tie = 0

    came_from: dict[Location, Location] = {}
    g_score: dict[Location, int] = {start: 0}

    heapq.heappush(open_heap, (heuristic(start, goal), tie, 0, start))

    while open_heap:
        _, _, g_current, current = heapq.heappop(open_heap)

        # skip outdated heap entries
        if g_current != g_score.get(current):
            continue
        
        # Goal reached, so reconstruct and return path
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path
        
        # Explore neighbors
        for nxt in get_neighbors(current):
            tentative_g = g_score[current] + get_cell_info_at(nxt).move_cost

            if tentative_g < g_score.get(nxt, 10**18):
                came_from[nxt] = current
                g_score[nxt] = tentative_g
                f = tentative_g + heuristic(nxt, goal)

                tie += 1
                heapq.heappush(open_heap, (f, tie, tentative_g, nxt))

    return None

def next_direction(current: Location, next_loc: Location) -> Direction:
    dx = next_loc.x - current.x
    dy = next_loc.y - current.y

    for d in DIR_ORDER:
        if d.dx == dx and d.dy == dy:
            return d
        
    return Direction.CENTER