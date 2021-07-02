class Debugger:
    colors = {
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "purple": "\033[35m",
        "cyan": "\033[36m",
        "white": "",
        "end": "\033[0m"
    }

    def __init__(self, debugging_mode=1):
        self.debugging_mode = debugging_mode

    def print(self, *args, **kwargs):
        color = "white"
        debugging_mode = 1

        if "color" in kwargs.keys():
            color = kwargs["color"]
            del kwargs["color"]
        elif "debugging_mode" in kwargs.keys():
            debugging_mode = kwargs["debugging_mode"]
            del kwargs["debugging_mode"]

        if 0 < debugging_mode <= self.debugging_mode:
            print(self.colors[color], end="")
            print(*args, **kwargs)
            print(self.colors["end"], end="")
