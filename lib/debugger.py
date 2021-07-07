class Debugger:
    colors = {
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "bright-red": "\033[91m",
        "bright-green": "\033[92m",
        "bright-yellow": "\033[93m",
        "bright-blue": "\033[94m",
        "bright-magenta": "\033[95m",
        "bright-cyan": "\033[96m",
        "white": "",
        "end": "\033[0m"
    }

    """
    TRIMS FILE TO THE FIRST n lines.
    USEFUL WHEN STUCK IN ENDLESS LOOPS CAUSING DEBUG FILE TO HAVE REPEATED INFO OVER AND OVER,
    CONSEQUENTLY HAVING ENORMOUS SIZE (WHICH CAN CAUSE MY IDE TO CRASH).
    """
    file_trimming_enabled = True
    max_line_count = 1000

    def __init__(self, debugging_mode=1, save_debugging_mode=1, save_log=False):
        # PRINT DEBUG OUTPUT
        self.debugging_mode = debugging_mode

        # WRITE DEBUG OUTPUT TO FILE
        self.save_debugging_mode = save_debugging_mode
        self.save_log = save_log
        if self.save_log:
            self.log_file = open("./debug.log", "w+")

        self.current_line_count = 0

    def print(self, *args, **kwargs):
        # DEFAULT ARGUMENTS
        color = "white"
        debugging_mode = 1

        # IF ARGUMENTS PASSED IN PRINT FUNCTION KWARGS REMOVE FROM THERE
        # AND UPDATE ABOVE VARIABLES WITH PASSED VALUES
        if "color" in kwargs.keys():
            color = kwargs["color"]
            del kwargs["color"]
        if "debugging_mode" in kwargs.keys():
            debugging_mode = kwargs["debugging_mode"]
            del kwargs["debugging_mode"]

        # PRINT DEBUG
        if 0 < debugging_mode <= self.debugging_mode:
            print(self.colors[color], end="")
            print(*args, **kwargs)
            print(self.colors["end"], end="")

        # STORE DEBUG TO LOG
        if 0 < self.save_debugging_mode <= self.save_debugging_mode and self.save_log:
            if self.file_trimming_enabled:
                if self.current_line_count <= self.max_line_count:
                    print(self.colors[color], end="", file=self.log_file)
                    print(*args, **kwargs, file=self.log_file)
                    print(self.colors["end"], end="", file=self.log_file)
                    self.current_line_count += 1
                # CLOSE THE LOG FILE WHEN LINES HAVE EXCEEDED THE MAXIMUM LINES ALLOWED
                elif self.current_line_count == self.max_line_count + 1:
                    self.close_log()
                    self.current_line_count += 1
            else:
                print(self.colors[color], end="", file=self.log_file)
                print(*args, **kwargs, file=self.log_file)
                print(self.colors["end"], end="", file=self.log_file)

    def close_log(self):
        if self.save_log:
            self.log_file.close()
