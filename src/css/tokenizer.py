"""
THE CSS TOKENIZER IS SUPPOSED TO CONVERT A STREAM OF CSS INTO A LIST OF CSS TOKENS.
"""
from src.css.preprocessor import CSSPreProcessor


# HELPER FUNCTIONS
def inside(iterable, char):
    if char in iterable and char != "":
        return True
    return False


class CSSTokenizer:
    # TERMS DEFINED IN SPECIFICATION
    newline = "\u000A"
    tab = "\u0009"
    space = "\u0020"
    whitespace = (newline, tab, space)

    digit = "01234567890"
    hex_digit = digit + "abcdef" + "ABCDEF"

    def __init__(self, stream):
        self.stream = stream

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
                self.reconsuming = False
        else:
            if not self.reconsuming:
                self.current_char = self.next_char
                self.next_char = "eof"
                self.index += step
            # RECONSUMING
            else:
                # SET RECONSUMPTION TO FALSE FOR NEXT CONSUMPTION
                self.reconsuming = False

        return self.current_char, self.next_char

    ####################################################################################
    # SPECIAL CONSUMES #################################################################
    def consume_comments(self):
        """
        ALGORITHM TO SKIP COMMENTS, RETURNS NONE.

        :return: None
        """
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
                self.token_buffer += current_char

    def consume_a_token(self):
        self.consume_comments()
        current_char, next_char = self.consume()

        if inside(self.whitespace, current_char):
            while inside(self.whitespace, current_char):
                current_char, next_char = self.consume()
            self.generate_new_token("whitespace-token")
            return self.token_buffer
        elif current_char == '"':
            self.consume_a_string_token()
            return self.token_buffer

    def tokenize(self):
        while self.index <= len(self.stream) or self.reconsuming:
            self.consume_a_token()
