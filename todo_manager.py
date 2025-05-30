def create_todo_file(objective: str, steps: list[str]):
    """
    Creates or overwrites a file named todo.md with the given objective and steps.
    """
    with open("todo.md", "w") as f:
        f.write(f"Objective: {objective}\n")
        f.write("Execute these tasks in order:\n")
        for step in steps:
            f.write(f"-{step}\n")

def read_todo_file():
    """
    Reads todo.md, parses it, and returns the objective and tasks.
    Returns {"objective": None, "tasks": []} if the file doesn't exist or is malformed.
    """
    try:
        with open("todo.md", "r") as f:
            lines = f.readlines()

        if not lines:
            return {"objective": None, "tasks": []}

        objective = None
        if lines[0].startswith("Objective: "):
            objective = lines[0][len("Objective: "):].strip()

        tasks = []
        tasks_started = False
        for line in lines:
            if line.strip() == "Execute these tasks in order:":
                tasks_started = True
                continue
            if tasks_started and line.startswith("-"):
                tasks.append(line[1:].strip())
        
        return {"objective": objective, "tasks": tasks}

    except FileNotFoundError:
        return {"objective": None, "tasks": []}

def reset_todo_file(objective: str):
    """
    Creates or overwrites todo.md with the given objective and an empty task list.
    """
    with open("todo.md", "w") as f:
        f.write(f"Objective: {objective}\n")
        f.write("Execute these tasks in order:\n")
