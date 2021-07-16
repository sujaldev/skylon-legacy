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
    def __init__(self, stream):
        self.stream = stream

        # PREPROCESSING STAGE
        self.preprocessor = CSSPreProcessor(stream)
        self.stream = self.preprocessor.process()

        self.current_char = ""
        self.next_char = ""
        self.index = 0

        # STATE VARIABLES
        self.reconsuming = False

    def consume(self):
        # UPDATE CHARACTERS
        if self.index < len(self.stream):
            if not self.reconsuming:
                # PUT NEXT CHAR IN CURRENT CHAR AND SET NEXT CHAR TO CURRENT INDEX
                self.current_char = self.next_char
                self.next_char = self.stream[self.index]
                # ONCE DONE UPDATING CHARACTERS MOVE AHEAD BY ONE
                self.index += 1
            # RECONSUMING
            else:
                # SET RECONSUMING TO FALSE FOR NEXT CONSUMPTION
                self.reconsuming = False
        else:
            if not self.reconsuming:
                self.current_char = self.next_char
                self.next_char = ""
                self.index += 1
            # RECONSUMING
            else:
                # SET RECONSUMPTION TO FALSE FOR NEXT CONSUMPTION
                self.reconsuming = False

        return self.current_char, self.next_char

    def consume_comments(self):
        pass

    def tokenize(self):
        while self.index <= len(self.stream):
            print(self.index, self.consume())
            if self.index == 2:
                self.reconsuming = True
                print(self.index, self.consume())


sample = CSSTokenizer("123456789")
sample.tokenize()
