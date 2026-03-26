from aegis_game.stub import *
import heapq

help_requests_sent = set()
claimed_help_targets = set()
claimed_survivor_targets = set()
current_target = None
needs_recharge = False
pending_scan = None
scan_results = {}

help_claim_counts = {}
HELP_RESPONSE_LIMIT = 1

LOW_ENERGY_THRESHOLD = 8
RECHARGE_THRESHOLD = 20
SCAN_DISTANCE_THRESHOLD = 2

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

def is_same_location(a: Location, b: Location) -> bool:
    return a.x == b.x and a.y == b.y

def target_is_still_valid(target: Location, survivors: list[Location]) -> bool:
    for surv in survivors:
        if is_same_location(target, surv):
            return True
    return False

def is_on_charging_cell(location: Location) -> bool:
    for charging_cell in get_charging_cells():
        if is_same_location(location, charging_cell):
            return True
    return False

def path_cost(path: list[Location]) -> int:
    total = 0

    for loc in path[1:]:
        total += get_cell_info_at(loc).move_cost

    return total

def choose_best_charging_cell(current: Location, target: Location) -> Location | None:
    charging_cells = get_charging_cells()

    if not charging_cells:
        return None

    best_cell = None
    best_score = float("inf")

    for charging_cell in charging_cells:
        to_charge = a_star(current, charging_cell)
        from_charge = a_star(charging_cell, target)

        if to_charge is None or from_charge is None:
            continue

        score = path_cost(to_charge) + path_cost(from_charge)

        if score < best_score:
            best_score = score
            best_cell = charging_cell

    return best_cell

def action_cost_at_target(target: Location) -> int:
    cell_info = get_cell_info_at(target)
    top_layer = cell_info.top_layer

    if isinstance(top_layer, Rubble):
        return top_layer.energy_required
    
    return 0


def think() -> None:

    global current_target
    global needs_recharge
    global pending_scan
    global scan_results
    
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

    for msg in messages:
        parts = msg.message.split()
        if len(parts) == 4 and parts[0] == "SCAN":
            sx = int(parts[1])
            sy = int(parts[2])
            agents_req = int(parts[3])
            scan_results[(sx, sy)] = agents_req

    for msg in messages:
        parts = msg.message.split()

        if len(parts) == 4 and parts[0] == "TARGET":
            x = int(parts[1])
            y = int(parts[2])
            claimed_survivor_targets.add((x, y))

    # First pass: collect claimed help targets
    # help_claim_counts.clear()

    for msg in messages:
        parts = msg.message.split()

        if len(parts) == 4 and parts[0] == "CLAIM":
            x = int(parts[1])
            y = int(parts[2])
            key = (x, y)
            claimed_help_targets.add(key)

            if key not in help_claim_counts:
                help_claim_counts[key] = 0
            help_claim_counts[key] =  help_claim_counts[key] + 1

    # Second pass: look at HELP requests that are not already claimed
    for msg in messages:
        parts = msg.message.split()

        if len(parts) == 4 and parts[0] == "HELP":
            x = int(parts[1])
            y = int(parts[2])
            requester_id = int(parts[3])

            if requester_id == my_id:
                continue

            loc = Location(x, y)
            key = (loc.x, loc.y)

            if help_claim_counts.get(key, 0) >= HELP_RESPONSE_LIMIT:
                continue

            if (loc.x, loc.y) in claimed_help_targets:
                continue

            dist = current.distance_to(loc)

            if dist < best_help_distance:
                best_help_distance = dist
                help_target = loc

        # Only send CLAIM if we decided to help AND nobody else has claimed it yet
    if help_target is not None:
        key = (help_target.x, help_target.y)
        if help_claim_counts.get(key, 0) < HELP_RESPONSE_LIMIT:
            send_message(f"CLAIM {help_target.x} {help_target.y} {my_id}", [])
            claimed_help_targets.add(key)
            if key not in help_claim_counts:
                help_claim_counts[key] = 0
            help_claim_counts[key] = help_claim_counts[key] + 1

    # Fetch the cell at the agent's current location.
    # If you want to check a different location, use `on_map(loc)` first
    # to ensure it's within the world bounds. The agent's own location is always valid.
    cell = get_cell_info_at(current)

    # Get the top layer at the agent's current location.
    # If a survivor is present, save it and end the turn.
    top_layer = cell.top_layer
    if isinstance(top_layer, Survivor):
        save()
        return
    
    if isinstance(top_layer, Rubble):
        log(f"Rubble here needs {top_layer.agents_required} agents and {top_layer.energy_required} energy.")
        
        send_message(f"SCAN {current.x} {current.y} {top_layer.agents_required}", [])

        
        agents_here = len(cell.agents)

        if agents_here >= top_layer.agents_required:
            dig()
            return
        
        # needs more than 1 agent, ask for help
        loc = get_location()
        if (loc.x, loc.y) not in help_requests_sent:
            send_message(f"HELP {loc.x} {loc.y} {get_id()}", [])  # Broadcast a help request with the location of the rubble
            help_requests_sent.add((loc.x, loc.y))

        move(Direction.CENTER)  # Stay in place to wait for teammates to help with the rubble
        return

    energy = get_energy_level()


    if energy <= LOW_ENERGY_THRESHOLD and not is_on_charging_cell(current):
        charging_target = choose_best_charging_cell(current, current)
        if charging_target is not None:
            needs_recharge = True
            emergency_path = a_star(current, charging_target)
            if emergency_path is not None and len(emergency_path) >= 2:
                move(next_direction(current, emergency_path[1]))
                return

    if is_on_charging_cell(current):
        if needs_recharge or energy < RECHARGE_THRESHOLD:
            recharge()
            if energy >= RECHARGE_THRESHOLD:
                needs_recharge = False
            return
    survivors = get_survs()

    if current_target is not None and help_target is None:
        if not target_is_still_valid(current_target, survivors):
            current_target = None

    new_target = None

    if help_target is not None:
        new_target = help_target
    elif survivors:
        sorted_survivors = sorted(survivors, key=lambda s: (s.x, s.y))
        num_survivors = len(sorted_survivors)

        assigned_index = (my_id - 1) % num_survivors
        new_target = sorted_survivors[assigned_index]

        log(f"Agent {my_id} assigned to survivor at {new_target}")
    else:
        move(Direction.CENTER) 
        return
    
    if current_target is None:
        current_target = new_target
    elif is_same_location(current, current_target):
        current_target = new_target
    elif new_target is not None and current.distance_to(new_target) + 5 < current.distance_to(current_target):
        current_target = new_target

    target = current_target
    
    if help_target is None and (target.x, target.y) not in claimed_survivor_targets:
        send_message(f"TARGET {target.x} {target.y} {my_id}", [])
        claimed_survivor_targets.add((target.x, target.y))

    target_key = (target.x, target.y)

    # Drone scan target if far away and not yet scanned
    if target_key not in scan_results and current.distance_to(target) > SCAN_DISTANCE_THRESHOLD:
        if pending_scan is not None and is_same_location(pending_scan, target):
            # Already waiting on result, just keep moving
            pass
        else:
            # Spend this turn scanning
            drone_scan(target)
            pending_scan = target
            return

    path = a_star(current, target)

    if path is not None:
        total_path_cost = path_cost(path)
        required_energy = total_path_cost + action_cost_at_target(target)

        if required_energy > energy:
            charging_target = choose_best_charging_cell(current, target)

            if charging_target is not None:
                if is_same_location(current, charging_target):
                    recharge()
                    return

                charging_path = a_star(current, charging_target)
                if charging_path is not None:
                    charging_cost = path_cost(charging_path)
                    if charging_cost <= energy:
                        log(f"Switching to charging path at {charging_target}")
                        needs_recharge = True
                        path = charging_path

    if path is None or len(path) < 2:
        move(Direction.CENTER)
        return

    next_loc = path[1]
    direction = next_direction(current, next_loc)
    move(direction)
        

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