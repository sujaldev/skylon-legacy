"""
THE CSS TOKENIZER IS SUPPOSED TO CONVERT A STREAM OF CSS INTO A LIST OF CSS TOKENS.
"""
from src.css.preprocessor import CSSPreProcessor
from lib.debugger import Debugger


# HELPER FUNCTIONS
def inside(iterable, char):
    if char in iterable and char != "":
        return True
    return False


# noinspection PyMethodMayBeStatic
class CSSTokenizer:
    # TERMS DEFINED IN SPECIFICATION
    newline = "\u000A"
    tab = "\u0009"
    space = "\u0020"
    whitespace = (newline, tab, space)

    digit = "01234567890"
    hex_digit = digit + "abcdef" + "ABCDEF"

    debug_table_width = (60, 100)

    def __init__(self, stream, debug_lvl=0, save_debugging_lvl=0, save_debug=False):
        self.stream = stream

        # DEBUGGER
        self.debug_lvl = debug_lvl
        self.save_debugging_lvl = save_debugging_lvl
        self.save_debug = save_debug
        self.debugger = Debugger(self.debug_lvl, self.save_debugging_lvl, self.save_debug)
        self.dprint = self.debugger.print
        self.debug_stack = []

        # PREPROCESSING STAGE
        self.preprocessor = CSSPreProcessor(stream)
        self.stream = self.preprocessor.process()

        # READ HEAD
        self.current_char = ""
        self.next_char = ""
        self.index = 0

        # STATE VARIABLES
        self.reconsuming = False

        # BUFFERS
        self.temp_buffer = ""
        self.token_buffer = {}

        # OUTPUT
        self.output = []

    ####################################################################################
    # DEBUGGING FUNCS ##################################################################
    def debug_append(self, function_name, char_tuple=None, color=""):
        if char_tuple is None:
            char_tuple = (self.current_char, self.next_char)

        if color == "":
            color = "blue"

        self.debug_stack.append((function_name, char_tuple, color))

    def display_debug_stack(self):
        func_width = self.debug_table_width[0]
        char_width = self.debug_table_width[1]

        report = f"┏{'━' * func_width}┳{'━' * char_width}┓\n"
        for call in self.debug_stack:
            func_display = " " * (func_width // 2 - len(call[0]) // 2) + call[0]
            func_display += " " * (func_width - len(func_display))

            char_display = f"{str(call[1])}"
            char_display += " " * (char_width - len(char_display))

            color = Debugger.colors[call[2]]
            report += f"┃{color}{func_display}\033[34m┃{char_display}┃\n" \
                      f"┃{'┈' * (func_width // 2 - 3)}  ↓  {'┈' * (func_width // 2 - 2)}┃{'┈' * char_width}┃\n"

        report += "┗" + "━" * func_width + "┻" + "━" * char_width + "┛"
        self.dprint(report, color="blue")

    ####################################################################################
    # CHECKS ###########################################################################
    def starts_with_valid_escape(self, current_char=None, next_char=None):
        if current_char is None:
            current_char = self.current_char
        if next_char is None:
            next_char = self.next_char

        if current_char != "\\":
            return False
        elif next_char == "\n":
            return False
        else:
            return True

    def is_non_ascii_code_point(self, char):
        try:
            return ord(char) >= 128
        except TypeError:
            return False

    def is_identifier_start(self, char):
        return char.isalpha() or self.is_non_ascii_code_point(char) or char == "_"

    def is_identifier(self, char):
        if char == "eof":
            return False
        return self.is_identifier_start(char) or char.isdigit() or char == "-"

    def is_non_printable_code_point(self, char):
        point = ord(char)
        return 0 <= point <= point or char == "\t" or 14 <= point <= 31 or point == 127

    def three_code_points_start_identifier(self, first_char=None, second_char=None, third_char=None):
        if first_char is None:
            first_char = self.current_char
        if second_char is None:
            second_char = self.next_char
        if third_char is None:
            third_char = self.nth_next_char()

        if first_char == "-":
            return self.is_identifier_start(second_char) or second_char == "-" or \
                   self.starts_with_valid_escape(second_char, third_char)
        elif self.is_identifier_start(first_char):
            return True
        elif first_char == "\\":
            return self.starts_with_valid_escape(first_char, second_char)
        else:
            return False

    def three_code_points_start_number(self, first_char=None, second_char=None, third_char=None):
        if first_char is None:
            first_char = self.current_char
        if second_char is None:
            second_char = self.next_char
        if third_char is None:
            third_char = self.nth_next_char()

        if inside(["+", "-"], first_char):
            if second_char.isdigit():
                return True
            elif second_char == "." and third_char.isdigit():
                return True
            else:
                return False
        elif first_char == ".":
            return second_char.isdigit()
        elif first_char.isdigit():
            return True
        else:
            return False

    def generate_new_token(self, token_name):
        # GENERATES A NEW TOKEN AND PLACES IT IN TOKEN BUFFER

        self.token_buffer = {
            "token-type": token_name
        }

        # TOKENS THAT HAVE A VALUE
        tokens_with_value_param = [
            "indent-token",
            "function-token",
            "at-keyword-token",
            "hash-token",
            "string-token",
            "url-token",

            # DELIM TOKEN'S VALUE CAN ONLY CONTAIN ONE CHAR
            "delim-token"
        ]

        tokens_with_numeric_value_param = [
            "number-token",
            "percentage-token",
            "dimension-token"
        ]

        if token_name in tokens_with_value_param:
            self.token_buffer["value"] = ""
        elif token_name in tokens_with_numeric_value_param:
            self.token_buffer["numeric-value"] = None

        if token_name == "hash-token":
            self.token_buffer["type-flag"] = "unrestricted"  # DEFAULT VALUE FOR HASH TOKEN'S TYPE FLAG OTHER IS ID
        elif token_name == "number-token":
            self.token_buffer["type-flag"] = "integer"  # DEFAULT IS INTEGER AND OTHER IS NUMBER
        elif token_name == "dimension-token":
            self.token_buffer["type-flag"] = "integer"  # DEFAULT IS INTEGER AND OTHER IS NUMBER
            self.token_buffer["unit"] = ""  # CONTAINS ONE OR MORE CHARACTERS

        self.debug_append("GENERATE_NEW_TOKEN()", self.token_buffer, color="green")

    def consume(self, step=1):
        # UPDATE CHARACTERS
        if self.index < len(self.stream):
            if not self.reconsuming:
                # PUT NEXT CHAR IN CURRENT CHAR AND SET NEXT CHAR TO CURRENT INDEX
                self.current_char = self.next_char
                self.next_char = self.stream[self.index]
                # ONCE DONE UPDATING CHARACTERS MOVE AHEAD BY ONE
                self.index += step
            # RECONSUMING
            else:
                # SET RECONSUMING TO FALSE FOR NEXT CONSUMPTION
                self.debug_append("RECONSUMING", "", color="yellow")
                self.reconsuming = False
        else:
            if not self.reconsuming:
                self.current_char = self.next_char
                self.next_char = "eof"
                self.index += step
            # RECONSUMING
            else:
                # SET RECONSUMPTION TO FALSE FOR NEXT CONSUMPTION
                self.debug_append("RECONSUMING", "", color="yellow")
                self.reconsuming = False

        self.debug_append("CONSUME()", color="yellow")
        return self.current_char, self.next_char

    ####################################################################################
    # SPECIAL CONSUMES #################################################################
    def nth_next_char(self, n=1):
        try:
            return self.stream[self.index + (n - 1)]
        except IndexError:
            return "eof"

    def consume_comments(self):
        """
        ALGORITHM TO SKIP COMMENTS, RETURNS NONE.

        :return: None
        """

        # DEBUGGING
        self.debug_append("CONSUME_COMMENTS()")

        if self.stream[self.index:self.index + 2] == "/*":
            stream = self.stream[self.index + 2:]
            skip_index = (self.index + 2) + stream.find("*/")
            # END COMMENT PATTERN MATCH FOUND
            if skip_index != -1:
                self.index = skip_index + 2 + 1  # ADD 2 TO COMPENSATE FOR LENGTH OF */ AND 1 FOR NEXT_CHAR
                self.consume_comments()
            # MATCH NOT FOUND (I.E. NO MATCH TILL EOF)
            else:
                # GENERATE PARSE ERROR
                pass

        return

    def consume_escaped_code_point(self):
        current_char, next_char = self.consume()

        if inside(self.hex_digit, current_char):
            self.temp_buffer += current_char
            # CONSUME THE REST 5 DIGITS IF POSSIBLE
            for i in range(5):
                if inside(self.hex_digit, next_char):
                    self.temp_buffer += next_char
                else:
                    break
                current_char, next_char = self.consume()
            # CONSUMING WHITESPACE
            if inside(self.whitespace, next_char):
                while inside(self.whitespace, next_char):
                    current_char, next_char = self.consume()

            hex_repr = int(self.temp_buffer, base=16)
            # IF HEX_REPR IS NULL OR GREATER THAN THE MAXIMUM ALLOWED CODE POINT VALUE
            if hex_repr == 0 or hex_repr > 1114111:
                return "\uFFFD"  # RETURNING REPLACEMENT CHARACTER
            else:
                return chr(hex_repr)  # CONVERT HEX NUMBER TO ACTUAL CHARACTER

    def consume_a_string_token(self, ending_code_point=None):
        """
        ALGORITHM TO CONSUME A STRING.
        IT WILL EITHER RETURN A <STRING-TOKEN> OR A <BAD-STRING-TOKEN>
        """
        if ending_code_point is None:
            ending_code_point = self.current_char

        # DEBUGGING
        self.debug_append("CONSUME_A_STRING_TOKEN()")

        self.generate_new_token("string-token")

        while True:
            current_char, next_char = self.consume()

            if current_char == ending_code_point:
                return
            elif next_char == "eof":
                self.token_buffer["value"] += current_char
                # GENERATE PARSE ERROR FOR EOF IN STRING
                return
            elif current_char == "\n":
                # GENERATE PARSE ERROR FOR BAD STRING
                self.generate_new_token("bad-string")
                self.reconsuming = True
                return
            elif current_char == "\\":
                if next_char == "eof":
                    pass
                elif next_char == "\n":
                    self.consume()
                elif self.starts_with_valid_escape():
                    self.token_buffer["value"] += self.consume_escaped_code_point()
            else:
                self.token_buffer["value"] += current_char

    def consume_number(self):
        # STEP 1
        num_type = "integer"  # DEFAULT
        num_repr = ""

        # STEP 2
        if inside(["+", "-"], self.next_char):
            num_repr += self.next_char
            self.consume()

        # STEP 3
        while self.next_char.isdigit():
            self.consume()
            num_repr += self.current_char

        # STEP 4
        if self.next_char == "." and self.nth_next_char().isdigit():
            num_repr += self.next_char + self.nth_next_char()
            self.consume(2)
            num_type = "number"
            while self.next_char.isdigit():
                num_repr += self.next_char
                self.consume()

        # STEP 5
        if inside(["E", "e"], self.next_char):
            if inside(["+", "-"], self.nth_next_char()) and self.nth_next_char(2).isdigit():
                num_repr += self.next_char + self.nth_next_char() + self.nth_next_char(2)
                self.consume(3)
                num_type = "number"
                while self.next_char.isdigit():
                    num_repr += self.next_char
                    self.consume()
            elif self.nth_next_char().isdigit():
                num_repr += self.next_char + self.nth_next_char()
                self.consume(2)
                num_type = "number"
                while self.next_char.isdigit():
                    num_repr += self.next_char
                    self.consume()

        # STEP 6
        num_repr = int(num_repr)
        return num_type, num_repr

    def consume_numeric_token(self):
        number = self.consume_number()

        if self.three_code_points_start_identifier():
            self.generate_new_token("dimension-token")
            self.token_buffer["value"] = number[1]
            self.token_buffer["type-flag"] = number[0]
            self.token_buffer["unit"] = self.consume_an_identifier()
        elif self.next_char == "%":
            self.consume()
            self.generate_new_token("percentage-token")
            self.token_buffer["value"] = number[1]
            self.token_buffer["type-flag"] = number[0]
        else:
            self.generate_new_token("number-token")
            self.token_buffer["value"] = number[1]
            self.token_buffer["type-flag"] = number[0]

        return self.token_buffer

    def consume_ident_like_token(self):
        string = self.consume_an_identifier()

        current_char, next_char = self.consume()

        if string.lower() == "url" and next_char == "(":
            self.consume()
            while inside(self.whitespace, next_char) and inside(self.whitespace, self.nth_next_char()):
                current_char, next_char = self.consume()

            if inside(('"', "'") + self.whitespace, next_char):
                self.generate_new_token("function-token")
                self.token_buffer["value"] = string
            else:
                self.consume_url_token()
        elif self.next_char == "(":
            self.consume()
            self.generate_new_token("function-token")
            self.token_buffer["value"] = string
        else:
            self.generate_new_token("ident-token")
            self.token_buffer["value"] = string

        return self.token_buffer

    def consume_url_token(self):
        self.generate_new_token("url-token")

        while inside(self.whitespace, self.next_char):
            self.consume()

        while True:
            current_char, next_char = self.consume()

            if current_char == ")":
                return self.token_buffer
            elif current_char == "eof":
                # GENERATE PARSE ERROR
                return self.token_buffer
            elif inside(self.whitespace, current_char):
                while inside(self.whitespace, current_char):
                    current_char, next_char = self.consume()
                self.reconsuming = True
            elif inside(['"', "'", "("], current_char) or self.is_non_printable_code_point(current_char):
                # GENERATE PARSE ERROR
                self.generate_new_token("bad-url-token")
                self.consume_remnants_of_bad_url()
                return self.token_buffer
            elif current_char == "\\":
                if self.starts_with_valid_escape():
                    self.token_buffer["value"] += self.consume_escaped_code_point()
                else:
                    # GENERATE PARSE ERROR
                    self.generate_new_token("bad-url-token")
                    self.consume_remnants_of_bad_url()
                    return self.token_buffer
            else:
                self.token_buffer["value"] += current_char

    def consume_remnants_of_bad_url(self):
        while True:
            current_char, next_char = self.consume()

            if inside([")", "eof"], current_char):
                return
            elif self.starts_with_valid_escape():
                self.consume_escaped_code_point()

    def consume_an_identifier(self):
        result = ""
        current_char, next_char = self.current_char, self.next_char
        while True:
            if self.is_identifier(current_char):
                result += current_char
            elif self.starts_with_valid_escape():
                result += self.consume_escaped_code_point()
            else:
                self.reconsuming = True
                return result

    def consume_a_token(self):
        # DEBUGGING
        self.debug_append("CONSUME_A_TOKEN()")

        self.consume_comments()

        # RETURN DEBUGGING
        self.debug_append("[CONSUME_COMMENTS] -> [CONSUME_A_TOKEN()]")
        current_char, next_char = self.consume()

        self.dprint((self.current_char, self.next_char, self.reconsuming))

        # CONSUMING WHITESPACE
        if inside(self.whitespace, current_char):
            self.debug_append("CONSUMING WHITESPACE", color="red")

            while inside(self.whitespace, current_char):
                current_char, next_char = self.consume()
                self.reconsuming = True
            self.generate_new_token("whitespace-token")

            self.debug_append("FINISHED CONSUMING WHITESPACE", color="red")
        # CONSUMING STRING
        elif current_char == '"':
            self.debug_append("CONSUMING STRING", color="red")
            self.consume_a_string_token()
        # CONSUMING ID OR HEX DIGITS
        elif current_char == "#":
            next_next_char = self.nth_next_char()

            if self.is_identifier(next_char) or self.starts_with_valid_escape(next_char, next_next_char):
                self.generate_new_token("hash-token")

                if self.three_code_points_start_identifier():
                    self.token_buffer["type-flag"] = "id"
                self.token_buffer["value"] = self.consume_an_identifier()
            else:
                self.generate_new_token("delim-token")
                self.token_buffer["value"] = current_char
        elif current_char == "'":
            self.consume_a_string_token()
        elif current_char == "(":
            self.generate_new_token("(-token")
        elif current_char == ")":
            self.generate_new_token(")-token")
        elif current_char == "+":
            if self.three_code_points_start_number():
                self.reconsuming = True
                self.consume_numeric_token()
            else:
                self.generate_new_token("delim-token")
                self.token_buffer["value"] = current_char
        elif current_char == ",":
            self.generate_new_token("comma-token")
        elif current_char == "-":
            if self.three_code_points_start_number():
                self.reconsuming = True
                self.consume_numeric_token()
            elif next_char + self.nth_next_char() == "->":
                self.consume(2)
                self.generate_new_token("CDC-token")
            elif self.three_code_points_start_identifier():
                self.reconsuming = True
                self.consume_ident_like_token()
            else:
                self.generate_new_token("delim-token")
                self.token_buffer["value"] = current_char
        elif current_char == ".":
            if self.three_code_points_start_number():
                self.reconsuming = True
                self.consume_numeric_token()
            else:
                self.generate_new_token("delim-token")
                self.token_buffer["value"] = current_char
        elif current_char == ":":
            self.generate_new_token("colon-token")
        elif current_char == ";":
            self.generate_new_token("semicolon-token")
        elif current_char == "<":
            if next_char + self.nth_next_char() + self.nth_next_char(2) == "!--":
                self.consume(3)
                self.generate_new_token("CDO-token")
            else:
                self.generate_new_token("delim-token")
                self.token_buffer["value"] = current_char
        elif current_char == "@":
            if self.three_code_points_start_identifier(next_char, self.nth_next_char(), self.nth_next_char(2)):
                self.generate_new_token("at-keyword-token")
                self.token_buffer["value"] = self.consume_an_identifier()
            else:
                self.generate_new_token("delim-token")
                self.token_buffer["value"] = current_char
        elif current_char == "[":
            self.generate_new_token("[-token")
        elif current_char == "\\":
            if self.starts_with_valid_escape():
                self.reconsuming = True
                self.consume_ident_like_token()
            else:
                # GENERATE PARSE ERROR
                self.generate_new_token("delim-token")
                self.token_buffer["value"] = current_char
        elif current_char == "]":
            self.generate_new_token("]-token")
        elif current_char == "{":
            self.generate_new_token("{-token")
        elif current_char == "}":
            self.generate_new_token("}-token")
        elif current_char.isdigit():
            self.reconsuming = True
            self.consume_numeric_token()
        elif self.is_identifier_start(current_char):
            self.reconsuming = True
            self.consume_ident_like_token()
        elif current_char == "eof":
            self.generate_new_token("EOF-token")
        else:
            self.generate_new_token("delim-token")
            self.token_buffer["value"] = current_char

    def tokenize(self):
        while self.index <= len(self.stream) or self.reconsuming:
            # DEBUGGING
            self.debug_append("TOKENIZE()", color="magenta")

            # REPEATEDLY CONSUME A TOKEN
            self.consume_a_token()
            self.output.append(self.token_buffer)

            # RETURN DEBUGGING
            self.debug_append("CONSUMED A TOKEN", color="magenta")

            # EMTPY BUFFERS
            self.debug_append("FLUSHING BUFFERS", "", color="magenta")
            self.token_buffer = {}
            self.temp_buffer = ""

        # DEBUGGING
        self.dprint(f"INPUT: {[self.stream]}", color="green")
        self.dprint(f"OUTPUT: {self.output}\n", color="green")
        self.display_debug_stack()
