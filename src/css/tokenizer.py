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
                self.next_char = ""
                self.index += step
            # RECONSUMING
            else:
                # SET RECONSUMPTION TO FALSE FOR NEXT CONSUMPTION
                self.reconsuming = False

        return self.current_char, self.next_char

    def consume_comments(self):
        """
        ALGORITHM TO SKIP COMMENTS, RETURNS NONE.

        :return: None
        """
        if self.stream[self.index:self.index+2] == "/*":
            stream = self.stream[self.index+2:]
            skip_index = (self.index + 2) + stream.find("*/")
            # END COMMENT PATTERN MATCH FOUND
            if skip_index != -1:
                self.index = skip_index + 2  # ADD 2 TO COMPENSATE FOR LENGTH OF */
                self.consume_comments()
            # MATCH NOT FOUND (I.E. NO MATCH TILL EOF)
            else:
                # GENERATE PARSE ERROR
                pass

        return

    def consume_a_token(self):
        self.consume_comments()
        current_char, next_char = self.consume()

        if inside(self.whitespace, next_char):
            while inside(self.whitespace, next_char):
                current_char, next_char = self.consume()
            self.generate_new_token("whitespace-token")
            return self.token_buffer

    def tokenize(self):
        while self.index <= len(self.stream) or self.reconsuming:
            self.consume_a_token()


sample = CSSTokenizer("123456789")
sample.tokenize()
