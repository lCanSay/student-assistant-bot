import re
from collections import defaultdict

def format_free_rooms(raw_rooms: list[str]) -> str:
    BLACKLIST = ["ИХН", "ДМиС", "онлайн", "оффлайн", "Кунаева", "SEZPIT", "UniX", "Jastar City", "ОФП", "СМГ"]
    EXPLICIT_FLOORS = {"independence hall": 2, "726": 2, "777": 2}
    
    blacklisted_lower = [b.lower() for b in BLACKLIST]
    floors: dict[int | str, list[str]] = defaultdict(list)
    
    for room in raw_rooms:
        room_lower = room.lower()
        if any(b in room_lower for b in blacklisted_lower):
            continue
            
        matched_explicit = False
        for exp_room, floor_num in EXPLICIT_FLOORS.items():
            if exp_room in room_lower:
                floors[floor_num].append(room.strip())
                matched_explicit = True
                break
                
        if matched_explicit:
            continue
            
        digits_only = re.sub(r'\D', '', room)
        if digits_only:
            numeric_val = int(digits_only)
            if 1 <= numeric_val <= 99:
                floors[0].append(room.strip())
                continue
            
        match = re.match(r'^([1-4])\d{2,3}[a-zA-Z\(\)]*$', room.strip())
        if match:
            floor = int(match.group(1))
            floors[floor].append(room.strip())
        else:
            floors["Другие"].append(room.strip())
            
    if not floors:
        return ""
        
    lines = []
    num_floors = sorted([f for f in floors.keys() if isinstance(f, int)])
    
    for floor in num_floors:
        rooms_str = ", ".join(sorted(floors[floor]))
        lines.append(f"<b>{floor}-й этаж:</b> {rooms_str}")
        
    if "Другие" in floors:
        rooms_str = ", ".join(sorted(floors["Другие"]))
        lines.append(f"<b>Другие:</b> {rooms_str}")
        
    return "\n\n".join(lines)

rooms = ["86(KMA)", "216a", "3", "504", "Independence hall", "726", "Some text", "ДМиС аудитория"]
print(format_free_rooms(rooms))
